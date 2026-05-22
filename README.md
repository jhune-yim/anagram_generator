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
