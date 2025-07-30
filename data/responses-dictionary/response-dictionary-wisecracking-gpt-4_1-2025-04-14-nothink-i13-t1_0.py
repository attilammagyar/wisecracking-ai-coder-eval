# --- BEGIN GENERATED CODE ---
import collections.abc
import re

# Helper: Is this a "word" token? We'll call something "word" if it has a letter or digit or underscore.
_WORD_RE = re.compile(r"\w", flags=re.UNICODE)
def is_word(token):
    return bool(_WORD_RE.search(token))

def normalize_token(token):
    return token.lower()

def split_to_words(text):
    # Breaks text (like a dictionary key) into sequences of "words", skipping all non-word chars as separators
    # Returns: list of lowercase word strings
    return [w for w in re.findall(r"\w+", text.lower())]

class TrieNode:
    __slots__ = ("children", "dict_ids")

    def __init__(self):
        self.children = dict()
        self.dict_ids = set()  # All the dictionary entry ids that end at this node

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Builds a trie where each edge is a word (as split by \w+), case-insensitive.
    Also, for single token annotation, we do a fast dict lookup.
    """
    trie_root = TrieNode()
    single_word_map = dict()
    for phrase, dict_id in dictionary.items():
        words = split_to_words(phrase)
        if not words:  # skip empty entries
            continue
        # For single words, store for fast lookup
        if len(words) == 1:
            k = words[0]
            if k not in single_word_map:
                single_word_map[k] = set()
            single_word_map[k].add(dict_id)
        # Insert into trie for phrase/compound matching
        node = trie_root
        for w in words:
            if w not in node.children:
                node.children[w] = TrieNode()
            node = node.children[w]
        node.dict_ids.add(dict_id)
    # We'll package the index as a tuple:
    return (trie_root, single_word_map)

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate each token with the set of dict ids it participates in, as per the rules.
    """
    tokens = list(tokens)  # listify for multiple passes
    n = len(tokens)
    annotated_ids = [set() for _ in tokens]
    trie_root, single_word_map = dictionary_index

    is_word_flags = [is_word(t) for t in tokens]

    # 1. Per-token single-word annotation
    for idx, (tok, isw) in enumerate(zip(tokens, is_word_flags)):
        if not isw:
            continue
        norm = normalize_token(tok)
        if norm in single_word_map:
            annotated_ids[idx].update(single_word_map[norm])

    # 2. Compound/phrase annotation: sliding window starting at every word token
    for start in range(n):
        if not is_word_flags[start]:
            continue
        t_idx = start
        # We'll try every possible walking path, skipping *zero or more* sep tokens between word tokens
        node = trie_root
        word_positions = []
        indices_between_words = []

        # First, build (token_idx, token) pairs
        positions = []
        for idx in range(start, n):
            positions.append((idx, tokens[idx]))
        # Now, walk ahead in tokens, using only word tokens for matching trie path, collecting their indices
        cur = start
        cur_node = trie_root

        # For phrase matching, we keep:
        #   phrase_word_indices: indices where the word tokens (participating in the phrase) are
        #   all_indices: indices of all tokens between the first and last word tokens (inclusive)
        phrase_word_indices = []
        all_indices = []

        walk_idx = start
        while walk_idx < n:
            this_token = tokens[walk_idx]
            if is_word_flags[walk_idx]:
                w = normalize_token(this_token)
                if w in cur_node.children:
                    cur_node = cur_node.children[w]
                    phrase_word_indices.append(walk_idx)
                    if not all_indices:
                        all_indices.append(walk_idx)
                    else:
                        # Add in-between separator tokens since last word
                        last_word = phrase_word_indices[-2] if len(phrase_word_indices) >=2 else phrase_word_indices[-1]
                        # Between last_word (exclusive) and walk_idx (inclusive)
                        for ii in range(all_indices[-1]+1, walk_idx):
                            all_indices.append(ii)
                        all_indices.append(walk_idx)
                    # If we reach a terminal dictionary entry at this point in the walk
                    if cur_node.dict_ids:
                        # Figure out which tokens to annotate:
                        # - the word tokens: always
                        # - the "inner" separator tokens: all tokens strictly between first and last word-token indices (inclusive range: phrase_word_indices[0] .. phrase_word_indices[-1]),
                        #     but NOT the first or last token if they're separators

                        # We'll annotate all tokens in all_indices with the phrase id,
                        # except for any leading/trailing separators
                        span_start = phrase_word_indices[0]
                        span_end = phrase_word_indices[-1]
                        active_tokens = list(range(span_start, span_end+1))  # all tokens in the matched phrase
                        # Mark which ones are "word" tokens:
                        # Determine if leading token is not a word, and so should be skipped for annotation as per rules
                        # (though this will only happen if the initial token is a separator, which is against
                        # how the walk starts, but let's double check)
                        # Only annotate leading/trailing separator tokens if they're "inner", not at the edges

                        # For each in the span:
                        for idx_ in active_tokens:
                            # For word tokens, always annotate
                            if is_word_flags[idx_]:
                                annotated_ids[idx_].update(cur_node.dict_ids)
                            else:
                                # Only annotate separators that are not at the **very start or end** of the phrase span
                                if idx_ != span_start and idx_ != span_end:
                                    annotated_ids[idx_].update(cur_node.dict_ids)
                    # Keep advancing to try for longer matches that include more words
                else:
                    break
            walk_idx +=1
    # Compose result
    # Each token: (original token, annotation set)
    result = [(tok, annotated_ids[idx]) for idx, tok in enumerate(tokens)]
    return result
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


