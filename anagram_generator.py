"""
Functional-style realistic anagram phrase generator.

This version uses:

  * wordfreq, if installed, to rank words by realistic English frequency.

  * A system dictionary such as /usr/share/dict/words as the source of
    candidate English words.

  * Pivot-letter pruning: at each recursive step, choose the still-needed
    letter that appears in the fewest candidate words, and only branch on
    words containing that letter.

  * Lazy recursive search: `search_anagrams` is a generator and yields
    phrases one at a time. `find_anagrams` uses `itertools.islice` to take
    only the first `max_results`.

  * Functional-style state passing: recursive search receives a new
    Counter and a new phrase tuple rather than mutating shared state.

  * Post-hoc multiset deduplication: pivot pruning already eliminates
    most duplicate phrasings of the same word multiset, but a few slip
    through when two words in a multiset happen to share the pivot
    letter (e.g. anagram pairs like "stop"/"pots"). `dedupe_multisets`
    catches those by canonicalising each phrase into a sorted tuple of
    its words. Keeping dedup outside the search keeps both pieces
    simple and avoids conflict with the pivot ordering.

Tradeoff:

  This version is clearer and easier to reason about than the in-place
  mutation version, but it is usually slower because each recursive branch
  allocates a new Counter and a new phrase tuple.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator, Sequence
import random
import re

try:
    from wordfreq import zipf_frequency
except ImportError:
    zipf_frequency = None


DICTIONARY_PATHS = [
    "/usr/share/dict/words",
    "/usr/dict/words",
]

MIN_ZIPF = 2.5


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class WordEntry:
    """
    Candidate word plus its letter multiset and realism score.

    `frozen=True` prevents reassignment of fields.

    `eq=False` keeps identity-based equality instead of generating structural
    equality over the Counter field. This also avoids hash-related surprises
    for a frozen dataclass containing a mutable, unhashable Counter.

    The Counter itself is mutable in Python, but every function in this
    module treats `WordEntry.letters` as immutable by convention.
    """

    word: str
    letters: Counter
    score: float


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Keep only alphabetic characters and make lowercase."""
    return re.sub(r"[^a-z]", "", text.lower())


def word_score(word: str) -> float:
    """
    Score a word by how realistic or common it is.

    If wordfreq is installed, use its Zipf frequency score.
    Otherwise use a simple length-based fallback.
    """
    if zipf_frequency is not None:
        return zipf_frequency(word, "en")

    n = len(word)

    if n <= 2:
        return 0.5

    if n <= 6:
        return 2.0

    return 1.0


def can_make_word(word_counter: Counter, remaining: Counter) -> bool:
    """Return True iff word_counter fits inside remaining."""
    return all(remaining.get(ch, 0) >= n for ch, n in word_counter.items())


def subtract_counter(remaining: Counter, word_counter: Counter) -> Counter:
    """
    Return a new Counter equal to remaining - word_counter.

    Assumes can_make_word(word_counter, remaining) is True.
    """
    new_remaining = remaining.copy()

    for ch, n in word_counter.items():
        new_remaining[ch] -= n

        if new_remaining[ch] == 0:
            del new_remaining[ch]

    return new_remaining


def counter_has_coverage(remaining: Counter, available: set[str]) -> bool:
    """
    Return True iff every needed letter appears in at least one
    candidate word.
    """
    return set(remaining).issubset(available)


def choose_pivot(
    remaining: Counter,
    by_letter: dict[str, list[WordEntry]],
) -> str:
    """
    Pick the still-needed letter with the fewest candidate words.

    Any full anagram must consume this letter via some word, so
    branching only on words containing the pivot is sound and
    minimises the candidate count at each step.
    """
    return min(remaining, key=lambda ch: len(by_letter.get(ch, ())))


def fitting_candidates(
    bucket: Sequence[WordEntry],
    remaining: Counter,
    limit: int,
) -> list[WordEntry]:
    """
    Return the first `limit` entries from `bucket` that fit inside the
    remaining letters.

    Uses `islice` over a generator so we stop scanning as soon as we
    have enough -- equivalent in spirit to Haskell's `take n . filter p`.
    """
    return list(
        islice(
            (
                entry
                for entry in bucket
                if can_make_word(entry.letters, remaining)
            ),
            limit,
        )
    )


def jitter(candidates: list[WordEntry], rng: random.Random) -> list[WordEntry]:
    """
    Shuffle then re-sort by score and length.

    Python's sort is stable, so only entries with exactly equal
    (score, length) keys remain randomised. This adds mild variety
    without disturbing the main score-ranking.
    """
    shuffled = candidates[:]
    rng.shuffle(shuffled)

    return sorted(
        shuffled,
        key=lambda entry: (entry.score, len(entry.word)),
        reverse=True,
    )


def dedupe_multisets(phrases: Iterator[str]) -> Iterator[str]:
    """
    Yield each multiset of words only once.

    Pivot-letter pruning is local: it choose a good branching letter at
    each recursive state, but it does not impose a global canonical order
    on the words chosen. Therefore, the same multiset of words can still
    be reached through different traversal paths.

    Each phrase is canonicalised by sorting its words. The first phrase
    with a given canonical key is yielded; later ones with the same
    key are dropped.

    This keeps duplicate-removal separate from the core search logic.
    Memory cost is one tuple per distinct multiset encountered.
    """
    seen: set[tuple[str, ...]] = set()

    for phrase in phrases:
        key = tuple(sorted(phrase.split()))

        if key not in seen:
            seen.add(key)
            yield phrase


# ---------------------------------------------------------------------------
# Dictionary loading
# ---------------------------------------------------------------------------

def find_dictionary(paths: Sequence[str] = DICTIONARY_PATHS) -> str:
    """Find an available system dictionary."""
    for path in paths:
        if Path(path).exists():
            return path

    raise FileNotFoundError(
        "No system dictionary found. Edit DICTIONARY_PATHS or install "
        "a word list, for example `apt install wamerican` on Debian/Ubuntu."
    )


_WORD_RE = re.compile(r"[a-z]+")


def valid_dictionary_word(word: str) -> bool:
    """Return True iff `word` is a usable lowercase alphabetic dictionary word."""
    return len(word) >= 2 and bool(_WORD_RE.fullmatch(word))


def make_word_entry(word: str) -> WordEntry:
    """Build a WordEntry from a word string."""
    return WordEntry(
        word=word,
        letters=Counter(word),
        score=word_score(word),
    )


def word_is_realistic(entry: WordEntry) -> bool:
    """
    Return True iff `entry` passes the realism threshold.

    The threshold is applied only when wordfreq is installed.
    """
    if zipf_frequency is None:
        return True

    return entry.score >= MIN_ZIPF


def stream_unique(words: Iterable[str]) -> Iterator[tuple[str, ...]]:
    """
    Yield each word only the first time it appears.

    Streaming deduplication: avoids materialising the entire raw
    dictionary as a list or dict first.
    """
    seen: set[str] = set()

    for word in words:
        if word not in seen:
            seen.add(word)
            yield word


def load_words(letters: str) -> list[WordEntry]:
    """
    Load candidate words from the system dictionary.

    Pipeline:

        raw lines
          -> strip / lowercase
          -> filter to valid words
          -> deduplicate
          -> build WordEntry
          -> filter words that fit in the input letters
          -> filter by wordfreq realism threshold, if available
          -> sort by score and length, descending
    """
    dictionary_file = find_dictionary()
    total = Counter(letters)

    with open(dictionary_file, "r", encoding="utf-8", errors="ignore") as f:
        raw_words = (line.strip().lower() for line in f)
        valid_words = (w for w in raw_words if valid_dictionary_word(w))
        unique_words = stream_unique(valid_words)
        entries = (make_word_entry(w) for w in unique_words)

        usable = [
            entry
            for entry in entries
            if can_make_word(entry.letters, total)
            and word_is_realistic(entry)
        ]

    return sorted(
        usable,
        key=lambda entry: (entry.score, len(entry.word)),
        reverse=True,
    )


def build_letter_index(
    words: Iterable[WordEntry],
) -> dict[str, list[WordEntry]]:
    """
    Build a letter -> candidate words index.

    The ordering inside each bucket follows the globally sorted word
    list, so the most realistic words come first.
    """
    index: dict[str, list[WordEntry]] = defaultdict(list)

    for entry in words:
        for ch in set(entry.word):
            index[ch].append(entry)

    return dict(index)


# ---------------------------------------------------------------------------
# Search (lazy generator)
# ---------------------------------------------------------------------------

def search_anagrams(
    remaining: Counter,
    by_letter: dict[str, list[WordEntry]],
    current_phrase: tuple[str, ...],
    *,
    max_depth: int,
    candidates_per_step: int,
    rng: random.Random | None,
) -> Iterator[str]:
    """
    Lazily yield anagram phrases.

    The caller decides how many to take (typically via `islice`). No
    accumulator is threaded through and no early-break logic lives
    here -- the consumer closes the generator as soon as enough
    phrases have arrived.

    Pivot-letter pruning reduce branching and eliminates many duplicate
    orderings indirectly, but it does not by itself impose a global
    canonical ordering on word choices. Therefore, different traversal
    paths can still produce the same multiset of words in different
    orders. Those duplicates are removed outside the search by
    `dedupe_multisets`.

    Parameters
    ----------
    remaining:
        Letters still unused.

    by_letter:
        Index mapping each letter to candidate words containing it.

    current_phrase:
        Tuple of words chosen so far.

    max_depth:
        Maximum number of words allowed in a phrase.

    candidates_per_step:
        Maximum number of fitting candidates considered at each branch.

    rng:
        Optional random generator for deterministic variety among
        score-ties.
    """

    if not remaining:
        yield " ".join(current_phrase)
        return

    if len(current_phrase) >= max_depth:
        return

    pivot = choose_pivot(remaining, by_letter)
    bucket = by_letter.get(pivot, ())

    if not bucket:
        return

    candidates = fitting_candidates(
        bucket=bucket,
        remaining=remaining,
        limit=candidates_per_step,
    )

    if rng is not None:
        candidates = jitter(candidates, rng)

    for entry in candidates:
        yield from search_anagrams(
            remaining=subtract_counter(remaining, entry.letters),
            by_letter=by_letter,
            current_phrase=current_phrase + (entry.word,),
            max_depth=max_depth,
            candidates_per_step=candidates_per_step,
            rng=rng,
        )


def find_anagrams(
    letters: str,
    words: Sequence[WordEntry],
    *,
    max_results: int = 10,
    max_depth: int = 6,
    candidates_per_step: int = 200,
    seed: int | None = None,
) -> list[str]:
    """
    Public search entry point.

    Builds the letter index, checks coverage, creates the RNG once if
    needed, runs the lazy search through the multiset deduper, and
    materialises up to `max_results` phrases.
    """
    by_letter = build_letter_index(words)
    remaining = Counter(letters)

    if not counter_has_coverage(remaining, set(by_letter)):
        return []

    rng = random.Random(seed) if seed is not None else None

    raw_phrases = search_anagrams(
        remaining=remaining,
        by_letter=by_letter,
        current_phrase=(),
        max_depth=max_depth,
        candidates_per_step=candidates_per_step,
        rng=rng,
    )

    return list(islice(dedupe_multisets(raw_phrases), max_results))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Realistic Anagram Maker ===")
    print("Enter a phrase. Spaces and punctuation are ignored.\n")

    phrase = input("Phrase: ")
    letters = clean_text(phrase)

    if not letters:
        print("Please enter at least one alphabetic character.")
        return

    print(f"\nLetters used: {letters}")
    print("Loading dictionary...")

    try:
        words = load_words(letters)
    except FileNotFoundError as e:
        print(e)
        return

    if not words:
        print("No possible words found.")
        return

    print(f"Kept {len(words)} candidate words. Searching...\n")

    anagrams = find_anagrams(
        letters,
        words,
        max_results=10,
        max_depth=6,
        candidates_per_step=200,
        seed=None,
    )

    if not anagrams:
        print("No full anagram phrase found.")

        if zipf_frequency is None:
            print("Tip: install wordfreq for better results:")
            print("    pip install wordfreq")

        return

    print("Possible anagrams:")

    for i, anagram in enumerate(anagrams, start=1):
        print(f"{i}. {anagram}")


if __name__ == "__main__":
    main()
