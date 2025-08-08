# --- BEGIN GENERATED CODE ---
import collections.abc
import re


def _is_word_token(s: str) -> bool:
    # Word tokens are strictly alphanumeric (no punctuation mixed in).
    return s.isalnum()


def _lower(s: str) -> str:
    return s.lower()


def _split_dict_words(text: str) -> list[str]:
    # Extract alphanumeric word chunks from a dictionary key, case-insensitive.
    # Separators (spaces, punctuation, markdown, etc.) are ignored.
    return re.findall(r'[0-9A-Za-z]+', text.lower())


class _TrieNode:
    __slots__ = ("children", "end_ids")

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.end_ids: set = set()


class _DictionaryIndex:
    __slots__ = ("word_map", "word_prefixes", "phrase_root")

    def __init__(self) -> None:
        self.word_map: dict[str, set] = {}
        self.word_prefixes: set[str] = set()
        self.phrase_root: _TrieNode = _TrieNode()


def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.

    Parameters:
        dictionary: Mapping strings (keys) to meanings (values).
    """
    idx = _DictionaryIndex()

    # Build index structures
    for key, value in dictionary.items():
        words = _split_dict_words(key)
        if not words:
            # Ignore entries that have no alphanumeric words.
            continue
        if len(words) == 1:
            w = words[0]
            s = idx.word_map.get(w)
            if s is None:
                s = set()
                idx.word_map[w] = s
            s.add(value)
            # Add all prefixes for pruning during concatenation scan
            for i in range(1, len(w) + 1):
                idx.word_prefixes.add(w[:i])
        else:
            # Insert phrase into trie
            node = idx.phrase_root
            for w in words:
                ch = node.children.get(w)
                if ch is None:
                    ch = _TrieNode()
                    node.children[w] = ch
                node = ch
            node.end_ids.add(value)

    return idx


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.

    Parameters:
        dictionary_index:   A dictionary index created by build_dictionary_index()
        tokens:             The tokens to be annotated.

    Return:
        annotated_tokens:   A list containing (token, annotations) pairs for each token in tokens.
    """
    # Unpack index
    idx = dictionary_index
    word_map: dict[str, set] = idx.word_map
    word_prefixes: set[str] = idx.word_prefixes
    phrase_root: _TrieNode = idx.phrase_root

    toks = list(tokens)
    n = len(toks)
    annotations = [set() for _ in range(n)]
    is_word = [_is_word_token(t) for t in toks]
    low = [_lower(t) if is_word[i] else toks[i] for i, t in enumerate(toks)]

    # 1) Single-word and cross-token "compound word" matches (no separators allowed).
    #    Concatenate adjacent word tokens and check against word_map using prefix pruning.
    for i in range(n):
        if not is_word[i]:
            continue
        s = low[i]
        # Single-token match
        if s in word_map:
            for val in word_map[s]:
                annotations[i].add(val)
        j = i
        # Extend over adjacent word tokens
        while j + 1 < n and is_word[j + 1]:
            s2 = s + low[j + 1]
            if s2 not in word_prefixes:
                break
            j += 1
            s = s2
            if s in word_map:
                ids = word_map[s]
                for k in range(i, j + 1):
                    annotations[k].update(ids)

    # 2) Multiword phrase matching via trie, ignoring separators between words.
    # Active state structure:
    #   {
    #       'node': trie node after last matched word,
    #       'start': index of first word token of the phrase,
    #       'last': index of last matched word token,
    #       'covered_seps': list of separator indices between matched words,
    #       'pending_seps': list of separator indices after last matched word
    #                       waiting for the next word,
    #   }
    active_states = []

    def annotate_phrase_range(start_idx: int, end_idx: int, sep_idxs: list[int], ids: set):
        # Annotate all word tokens from start to end and all inner separators.
        for k in range(start_idx, end_idx + 1):
            annotations[k].update(ids)
        for si in sep_idxs:
            annotations[si].update(ids)

    for i in range(n):
        if is_word[i]:
            w = low[i]
            new_states = []
            # Advance existing states if possible
            for st in active_states:
                child = st['node'].children.get(w)
                if child is not None:
                    st2 = {
                        'node': child,
                        'start': st['start'],
                        'last': i,
                        'covered_seps': st['covered_seps'] + st['pending_seps'],
                        'pending_seps': [],
                    }
                    # Annotate for any phrase ending here (nested and overlapping supported)
                    if child.end_ids:
                        annotate_phrase_range(st2['start'], st2['last'], st2['covered_seps'], child.end_ids)
                    new_states.append(st2)
                else:
                    # Cannot advance this state -> drop it
                    pass

            # Start new states from this word
            child = phrase_root.children.get(w)
            if child is not None:
                st0 = {
                    'node': child,
                    'start': i,
                    'last': i,
                    'covered_seps': [],
                    'pending_seps': [],
                }
                if child.end_ids:
                    annotate_phrase_range(st0['start'], st0['last'], st0['covered_seps'], child.end_ids)
                new_states.append(st0)

            active_states = new_states
        else:
            # Separator: collect as pending for all running states
            if active_states:
                for st in active_states:
                    st['pending_seps'].append(i)

    # Stitch back tokens with their annotations
    return [(toks[i], annotations[i]) for i in range(n)]
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


