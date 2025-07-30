# --- BEGIN GENERATED CODE ---
import collections.abc
import re
from collections import defaultdict

# Helper: normalize words and separators for matching: casefold, trim.
def normalize(s: str) -> str:
    return s.casefold()

# Helper: For simplicity, use "\w+" for words, else separator; extend as needed for full Unicode support.
WORD_RE = re.compile(r'\w+', re.UNICODE)

def is_word(token: str) -> bool:
    return bool(WORD_RE.fullmatch(token))

def split_phrase_to_tokens(s: str):
    """
    Split a phrase in the dictionary into a sequence of ('w', word) and ('s', separator) tokens,
    for use in phrase trie.
    All words/separators are lowercased and normalized.
    """
    # We'll split as alternating word/separator.
    out = []
    pos = 0
    length = len(s)
    while pos < length:
        match = WORD_RE.match(s, pos)
        if match:
            out.append(('w', normalize(match.group())))
            pos = match.end()
        else:
            # Find the next word, treat it as separator
            sep_start = pos
            while pos < length and not WORD_RE.match(s, pos):
                pos += 1
            out.append(('s', s[sep_start:pos].lower()))
    return out

class TrieNode:
    __slots__ = ["children", "dict_entry_ids"]
    def __init__(self):
        # children: {'w': {token: TrieNode}, 's': {sep: TrieNode}}
        self.children = {'w': {}, 's': {}}
        self.dict_entry_ids = set()
    def add(self, tokens, dict_entry_id):
        node = self
        for kind, val in tokens:
            if val not in node.children[kind]:
                node.children[kind][val] = TrieNode()
            node = node.children[kind][val]
        node.dict_entry_ids.add(dict_entry_id)
    def __repr__(self):
        return f"<TrieNode children={self.children!r}, ids={self.dict_entry_ids}>"

class DictionaryIndex:
    __slots__ = ["word_dict", "phrase_trie"]
    def __init__(self):
        self.word_dict = defaultdict(set)  # word(str) -> set of entry ids
        self.phrase_trie = TrieNode()

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.
    """
    idx = DictionaryIndex()
    for phrase, entry_id in dictionary.items():
        # Split into word/separators for phrase trie
        token_list = split_phrase_to_tokens(phrase)
        # If it's a single word: add to word_dict for fast lookup
        nonsep = [wv for kind, wv in token_list if kind == 'w']
        nonsep_count = len(nonsep)
        sep_count = len(token_list) - nonsep_count
        if nonsep_count == 1 and sep_count == 0:
            idx.word_dict[normalize(nonsep[0])].add(entry_id)
        else:
            # For phrases or multiword "compounds"
            idx.phrase_trie.add(token_list, entry_id)
            # Also support single tokens that could be compounds with no separator ('AAABBB')
            if nonsep_count == 1 and sep_count > 0:
                idx.word_dict[normalize(nonsep[0])].add(entry_id)
    return idx

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.
    """
    tokens = list(tokens)
    N = len(tokens)
    annotations = [set() for _ in range(N)]

    # Precompute a list telling us if a token is a word (True) or separator (False).
    kinds = ['w' if is_word(tok) else 's' for tok in tokens]
    norm_tokens = [normalize(tok) for tok in tokens]

    idx = dictionary_index

    # 1. Single-word lookup
    for i, (kind, norm_tok) in enumerate(zip(kinds, norm_tokens)):
        if kind == 'w':
            if norm_tok in idx.word_dict:
                annotations[i].update(idx.word_dict[norm_tok])

    # 2. Phrase/compound phrase lookups using trie

    for start in range(N):
        # Skip leading separators -- required by the spec
        if kinds[start] == 's':
            continue
        # Try to match longest phrase from this word token
        spans = [] # Each is: (end_idx_exclusive, set_of_entry_ids)
        trie_node = idx.phrase_trie
        pos = start
        consumed_tokens = 0    # Number of inner word tokens we've matched
        last_match = None  # (end_idx, dict_ids)
        curr_pos = pos
        # We'll gather matches as we go.
        # The trie may descend, skipping separators in token stream.

        node = trie_node
        j = curr_pos
        token_kindval = []
        while j < N:
            k = kinds[j]
            v = None
            if k == 'w':
                v = norm_tokens[j]
            else:
                v = tokens[j].lower()
            # Is there a step for this kind?
            if v in node.children[k]:
                node = node.children[k][v]
                token_kindval.append((j, k))
                if node.dict_entry_ids:
                    # Candidate match: should consist only of word tokens surrounded by
                    # zero or more separators (which are only inner, i.e., the phrase must begin and end with word tokens).
                    # The window: start ... j (inclusive)
                    # Only mark separators that are not leading/trailing within this window.
                    first_word = start
                    last_word = j
                    # annotate from first_word up to last_word, include separators between, but not before/after
                    # For all tokens in [first_word, last_word+1), but only mark separators that aren't at ends.
                    for entry_id in node.dict_entry_ids:
                        for p in range(first_word, last_word + 1):
                            if (p == first_word or p == last_word):
                                if kinds[p] == 'w':
                                    annotations[p].add(entry_id)
                            else:
                                # Inner positions: annotate both words and separators (if any)
                                annotations[p].add(entry_id)
                j += 1
            else:
                # If word: do not allow skipping word tokens in the trie.
                # If separator in the stream, but not separator in the trie, we can skip input separators.
                if k == 's':
                    j += 1
                    continue
                break
            # else: break

    # Compose results
    for tok, ann in zip(tokens, annotations):
        yield (tok, set(ann))
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


