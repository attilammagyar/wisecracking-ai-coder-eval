# --- BEGIN GENERATED CODE ---
import collections.abc

# --------------------------
# Helpers and trie structures
# --------------------------

def _is_word_token(token: str) -> bool:
    # Word = all alphanumerics, non-empty. Everything else is a separator token.
    return bool(token) and all(ch.isalnum() for ch in token)

def _split_words_lower(s: str) -> list[str]:
    # Split a dictionary entry into lowercase "word" chunks by non-alnum separators.
    s = s.lower()
    words = []
    cur = []
    for ch in s:
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                words.append("".join(cur))
                cur = []
    if cur:
        words.append("".join(cur))
    return words


class _CharTrieNode:
    __slots__ = ("children", "terminal_word")
    def __init__(self):
        self.children: dict[str, _CharTrieNode] = {}
        self.terminal_word: str | None = None  # the full word string if terminal


class _PhraseTrieNode:
    __slots__ = ("children", "meanings")
    def __init__(self):
        self.children: dict[str, _PhraseTrieNode] = {}
        self.meanings: set = set()  # set of dictionary entry identifiers


# --------------------------
# Public API
# --------------------------

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.

    Parameters:
        dictionary: Mapping strings (keys) to meanings (values).
    """
    # Build a char-trie for all dictionary "words" (contiguous alnum sequences)
    # and a phrase-trie over sequences of these words.
    char_root = _CharTrieNode()
    phrase_root = _PhraseTrieNode()

    # Collect unique dictionary words to populate the char trie once.
    unique_words = set()

    for key, meaning in dictionary.items():
        words = _split_words_lower(key)
        if not words:
            # If a dictionary key has no word characters at all, it's useless for our matching.
            continue

        # Insert into phrase trie
        node = phrase_root
        for w in words:
            child = node.children.get(w)
            if child is None:
                child = _PhraseTrieNode()
                node.children[w] = child
            node = child
        node.meanings.add(meaning)

        # Collect words for char trie
        unique_words.update(words)

    # Build char trie from all unique words
    for w in unique_words:
        node = char_root
        for ch in w:
            nxt = node.children.get(ch)
            if nxt is None:
                nxt = _CharTrieNode()
                node.children[ch] = nxt
            node = nxt
        node.terminal_word = w  # if duplicates, it's the same word string anyway

    # Return both tries as the index
    return {"char_root": char_root, "phrase_root": phrase_root}


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.

    Parameters:
        dictionary_index:   A dictionary index created by build_dictionary_index()
        tokens:             The tokens to be annotated.

    Return:
        annotated_tokens:   A list containing (token, annotations) pairs for each token in tokens.
    """
    tokens = list(tokens)
    n = len(tokens)
    if n == 0:
        return []

    char_root: _CharTrieNode = dictionary_index["char_root"]
    phrase_root: _PhraseTrieNode = dictionary_index["phrase_root"]

    # Precompute token types and lowercase forms for word tokens
    is_word = [False] * n
    word_norm = [None] * n
    for i, t in enumerate(tokens):
        if _is_word_token(t):
            is_word[i] = True
            word_norm[i] = t.lower()

    # Prepare annotation sets
    anns = [set() for _ in range(n)]

    # Cache for word matches starting at a position:
    # position -> list of (end_pos_exclusive, matched_word_string)
    word_matches_cache: dict[int, list[tuple[int, str]]] = {}

    def word_matches_from(pos: int) -> list[tuple[int, str]]:
        """
        Find all dictionary 'word' matches starting at pos by concatenating
        adjacent word tokens (no separators allowed in between).
        Matches end only at token boundaries (no mid-token cuts).
        """
        if pos in word_matches_cache:
            return word_matches_cache[pos]

        res = []
        if pos >= n or not is_word[pos]:
            word_matches_cache[pos] = res
            return res

        node = char_root
        j = pos
        while j < n and is_word[j]:
            w = word_norm[j]
            # Walk the char trie across all characters of token j
            for ch in w:
                nxt = node.children.get(ch)
                if nxt is None:
                    # No further path; stop searching further tokens
                    word_matches_cache[pos] = res
                    return res
                node = nxt
            # Only accept terminal at token boundary
            if node.terminal_word is not None:
                res.append((j + 1, node.terminal_word))
            j += 1

        word_matches_cache[pos] = res
        return res

    # Explore matches starting at each word token
    for start in range(n):
        if not is_word[start]:
            continue

        first_matches = word_matches_from(start)
        if not first_matches:
            continue

        # DFS through the phrase trie: extend by (separator+word)* steps
        def explore(phrase_node: _PhraseTrieNode, end_pos: int):
            # Annotate current phrase node if it's a terminal
            if phrase_node.meanings:
                # Annotate every token in [start, end_pos) — this covers words and
                # the inner separators between them, but never leading/trailing separators.
                for idx in range(start, end_pos):
                    anns[idx].update(phrase_node.meanings)

            # Try to extend with (>=1 separators) + next word
            p = end_pos
            if p >= n or is_word[p]:
                return  # need at least one separator token to continue a multi-word phrase

            # Consume one or more separator tokens
            while p < n and not is_word[p]:
                p += 1
            # Now p is the start of the next word (or end)
            if p >= n or not is_word[p]:
                return

            next_matches = word_matches_from(p)
            if not next_matches:
                return

            for nxt_end, nxt_word in next_matches:
                child = phrase_node.children.get(nxt_word)
                if child is not None:
                    explore(child, nxt_end)

        # Kick off exploration for each possible first dictionary word from 'start'
        for end1, word1 in first_matches:
            node1 = phrase_root.children.get(word1)
            if node1 is not None:
                explore(node1, end1)

    # Build the final (token, annotations) pairs
    annotated_tokens = [(tok, anns[i]) for i, tok in enumerate(tokens)]
    return annotated_tokens
# --- END GENERATED CODE ---

def test_empty_sentence():
    dictionary = {}
    tokens = []

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = []
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_token_not_in_dictionary():
    """
    When a token is not found in the dictionary
    then it should not be annotated with anything.
    """
    dictionary = {}
    tokens = ["AAA"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_token_found_in_dictionary():
    """
    When a token is found in the dictionary
    then the token should be annotated with its dictionary entry.
    """
    dictionary = {"AAA": 1}
    tokens = ["AAA"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_case_insensitive_dictionary_lookup():
    """
    Dictionary lookup should be case-insensitive.
    """
    dictionary = {"AAA": 1, "BBB": 2}
    tokens = ["Aaa", "bbb"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("Aaa", {1}), ("bbb", {2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase():
    """
    All tokens in a compound phrase which is found in the dictionary
    should be annotated with the dictionary entry of the phrase.
    """
    dictionary = {"AAA BBB": 1}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), (" ", {1}), ("BBB", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase_and_individual_word():
    """
    When a token is found in the dictionary both as an individual word and as part of a compound phrase
    then its annotations should include the dictionary entries of both the phrase and the individual word as well.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA BBB": 3}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {3, 1}), (" ", {3}), ("BBB", {3, 2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrases_word_separation():
    """
    Compound phrase dictionary lookup should be insensitive to word separators.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA, BBB": 3}
    tokens = ["AAA", " ", "*", "BBB", "*"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {3, 1}), (" ", {3}), ("*", {3}),("BBB", {3, 2}), ("*", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_leading_and_trailing_separators_around_compound_phrase():
    """
    The leading and trailing word separators should not be considered
    parts of a compound phrase.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA BBB": 3}
    tokens = [" ", "AAA", " ", "BBB", " "]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [(" ", set()), ("AAA", {3, 1}), (" ", {3}), ("BBB", {3, 2}), (" ", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_separated_tokens_do_not_make_a_compound_word():
    """
    When tokens are separated by non-word characters
    then they should not be considered a compound word.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAABBB": 3}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), (" ", set()), ("BBB", {2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_word_tokens_missing_from_dictionary():
    """
    Compound words may contain tokens which are not listed in the dictionary
    as individual words.
    """
    dictionary = {"AAABBB": 1}
    tokens = ["AAA", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), ("BBB", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase_overlap():
    """
    Tokens in overlapping compound phrases should be annotated with the
    dictionary entries for all compound phrases in which they participate.
    """
    dictionary = {
        "AAA": 1,
        "BBB": 2,
        "CCC": 3,
        "AAA BBB": 4,
        "BBB CCC": 5,
        "CCC CCC": 6,
    }
    tokens = ["AAA", " ", "BBB", " ", "CCC", " ", "CCC", " ", "CCC"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("AAA", {4, 1}),
        (" ", {4}),
        ("BBB", {5, 4, 2}),
        (" ", {5}),
        ("CCC", {6, 5, 3}),
        (" ", {6}),
        ("CCC", {6, 3}),
        (" ", {6}),
        ("CCC", {6, 3}),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_nested_compound_phrases():
    """
    When a compound phrase itself is a part of a larger compound phrase
    then its tokens should be annotated with the dictionary entries for all the nested compound phrases.
    """
    dictionary = {
        "AAA": 1,
        "BBB": 2,
        "CCC": 3,
        "DDD": 4,
        "EEE": 5,
        "AAA BBB CCC DDD EEE": 6,
        "BBB CCC DDD": 7,
        "BBB CCC": 8,
    }
    tokens = ["AAA", " ", "BBB", " ", "CCC", " ", "DDD", " ", "EEE"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("AAA", {6, 1}),
        (" ", {6}),
        ("BBB", {6, 7, 8, 2}),
        (" ", {6, 7, 8}),
        ("CCC", {6, 7, 8, 3}),
        (" ", {6, 7}),
        ("DDD", {6, 7, 4}),
        (" ", {6}),
        ("EEE", {6, 5}),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_no_midtoken_match():
    """
    Dictionary entry match must occur at token end.
    """
    dictionary = {"AA": 1, "AAA BBB": 2, "CC": 3, "CCCDDD": 4}
    tokens = ["AAA", " ", "BBBCCC", "CCC", "DDDEEE"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", set()), (" ", set()), ("BBBCCC", set()), ("CCC", set()), ("DDDEEE", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_real_life_example():
    dictionary = {
        "a": 1,
        "black": 2,
        "swan": 3,
        "black swan": 4,
        "event": 5,
        "black swan event": 6,
        "would": 7,
        "occur": 8,
        "less": 9,
        "than": 10,
        "once": 11,
        "in": 12,
        "blue": 13,
        "moon": 14,
        "blue moon": 15,
        "once in a blue moon": 16,
    }
    tokens = [
        "A", " ", "black", " ", "swan", " ", "event", " ", "would", " ",
        "occur", " ", "less", " ", "than", " ", "once", " ", "in", " ", "a",
        " ", "blue", " ", "moon", ".",
    ]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("A", {1}),
        (" ", set()),
        ("black", {2, 4, 6}),
        (" ", {4, 6}),
        ("swan", {3, 4, 6}),
        (" ", {6}),
        ("event", {5, 6}),
        (" ", set()),
        ("would", {7}),
        (" ", set()),
        ("occur", {8}),
        (" ", set()),
        ("less", {9}),
        (" ", set()),
        ("than", {10}),
        (" ", set()),
        ("once", {11, 16}),
        (" ", {16}),
        ("in", {12, 16}),
        (" ", {16}),
        ("a", {1, 16}),
        (" ", {16}),
        ("blue", {13, 15, 16}),
        (" ", {15, 16}),
        ("moon", {14, 15, 16}),
        (".", set()),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def perf_test():
    import random
    import time

    dictionary = {
        "a": 1,
        "black": 2,
        "swan": 3,
        "black swan": 4,
        "event": 5,
        "black swan event": 6,
        "would": 7,
        "occur": 8,
        "less": 9,
        "than": 10,
        "once": 11,
        "in": 12,
        "blue": 13,
        "moon": 14,
        "blue moon": 15,
        "once in a blue moon": 16,
    }
    tokens = [
        "A", " ", "black", " ", "swan", " ", "event", " ", "would", " ",
        "occur", " ", "less", " ", "than", " ", "once", " ", "in", " ", "a",
        " ", "blue", " ", "moon", ".",
    ]
    letters = "abcdefghijklmnopqrstuvwxyz"

    while len(dictionary) < 1000:
        random_word = "".join([random.choice(letters) for i in range(15)])
        random_expr = (
            "".join([random.choice(letters) for i in range(7)])
            + " "
            + "".join([random.choice(letters) for i in range(7)])
        )
        dictionary[random_word] = len(dictionary)
        dictionary[random_expr] = len(dictionary)

    for i in range(6):
        tokens = tokens + tokens

    begin = time.time()

    for i in range(100):
        tokens_copy = list(tokens)
        dictionary_copy = dict(dictionary)
        dictionary_index = build_dictionary_index(dictionary_copy)
        annotated_tokens = list(annotate(tokens_copy, dictionary_index))

    end = time.time()

    return end - begin


def run_tests():
    import json
    import sys

    module = sys.modules[__name__]

    tests = []

    for name, value in globals().items():
        if name.startswith("test_") and callable(value) and value.__code__.co_argcount == 0:
            tests.append(value)

    passed = 0
    failed = 0
    failures = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            failed += 1
            failures.append(f"{type(exc)} {exc}")

    perf = perf_test()

    results = {
        "passed": passed,
        "failed": failed,
        "perf": perf,
        "failures": failures,
    }

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run_tests()


