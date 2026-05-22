# Functional Anagram Generator

A functional-style Python anagram phrase generator.

This program takes an input phrase, ignores spaces and punctuation, and searches for phrases that can be made from exactly the same letters. It uses a system dictionary for candidate words and optionally uses [`wordfreq`](https://pypi.org/project/wordfreq/) to rank words by realistic English frequency.

The goal is not to produce perfect grammatical English. Rather, the project demonstrates a clean recursive search architecture using letter multisets, dictionary filtering, pivot-letter pruning, lazy generators, and post-hoc duplicate removal.

## Features

- Cleans user input by keeping only alphabetic characters.

- Uses `collections.Counter` to represent letter multisets.

- Loads candidate words from a system dictionary such as:

  ```text

  /usr/share/dict/words


## Mathematics behind it

An anagram is a word formed by rearranging the letters of another. A working anagram generator fits comfortably in 200 to 300 lines of Python. But is generating anagrams just a matter of procedurally shuffling letters? In fact, the task quietly draws on combinatorics, computational complexity, number theory and group theory.

Generating anagrams is, at heart, enumerating permutations. When every letter in the input is distinct, the number of possible anagrams equals the factorial of the word's length. The word CAT has three distinct letters and therefore admits $3! = 3 \times 2 \times 1 = 6$ arrangements.

When letters repeat, as in MISSISSIPPI, we cannot count identical rearrangements as separate anagrams. The right tool is the multinomial coefficient,

$$\frac{n!}{n_1!\, n_2!\, \cdots\, n_k!},$$

where $n$ is the total number of letters and $n_i$ is the multiplicity of the $i$-th distinct letter. MISSISSIPPI has eleven letters: one M, four I's, four S's, and two P's. Substituting,

$$\frac{11!}{1! \cdot 4! \cdot 4! \cdot 2!} = 34{,}650$$

distinct anagrams.

Anagram generation is a textbook example of $O(n!)$ time complexity. Factorial growth outstrips exponential growth, and the numbers escalate quickly: a five-letter word admits 120 arrangements; a ten-letter word, 3,628,800; a twenty-letter word, roughly $2.4 \times 10^{18}$. Even at $10^8$ arrangements generated per second, enumerating every permutation of a twenty-letter word would take about 770 years. That is brute-force computation displaying both its character and its limit.

If the question is not "enumerate every anagram" but rather "are these two strings anagrams of each other?", the Fundamental Theorem of Arithmetic supplies a particularly clean answer. The theorem states that every integer greater than $1$ has a unique factorisation into primes. Map each letter to a distinct prime — $A = 2$, $B = 3$, $C = 5$, and so on — and the product of a word's letter values becomes a fingerprint that is invariant under rearrangement. With $T = 71$, $A = 2$, $R = 61$, we obtain $TAR = 71 \times 2 \times 61 = 8662$, $RAT = 61 \times 2 \times 71 = 8662$, and $ART = 2 \times 61 \times 71 = 8662$. By unique factorisation, no other combination of letters can yield $8662$ under this mapping; two strings are anagrams of each other if and only if their prime products are equal.

The trick is mathematically elegant but has a practical wrinkle: the product grows quickly. Across the 26-letter English alphabet, the largest prime required is $101$, so a word of length $n$ can produce a product on the order of $101^n$. Around $n = 10$ this exceeds the range of a 64-bit C integer and overflows; Python absorbs the cost transparently thanks to its arbitrary-precision integers. In practice, anagram detection is more commonly done by comparing sorted strings — $O(n \log n)$ — or by comparing letter multisets with a `Counter`, which runs in $O(n)$.

Construed narrowly, the algebraic study of rearranging elements is group theory. The set of all permutations of $n$ distinct symbols, equipped with the operation of composition, forms the symmetric group, denoted $S_n$. Writing an algorithm that swaps letters and enumerates all arrangements is, mathematically, an exploration of the structure of $S_n$.
