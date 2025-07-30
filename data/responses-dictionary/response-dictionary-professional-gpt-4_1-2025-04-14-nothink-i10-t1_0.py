# --- BEGIN GENERATED CODE ---
import collections.abc

# Helper: check if token is "word" (contains any alphanumeric) or "separator"
def is_word_token(token):
    # Any Unicode alphanumeric is a word
    return any(c.isalnum() for c in token)

def normalize_token(token):
    return token.lower()

_SPECIAL_SEP = "__SEP__"  # Sentinel in the trie to stand for separator

# Trie node for dictionary entry (for phrases)
class PhraseTrieNode:
    __slots__ = ("children", "dict_ids")

    def __init__(self):
        self.children = dict()  # mapping (normalized token or _SPECIAL_SEP) -> PhraseTrieNode
        self.dict_ids = set()   # All dict IDs ending at this node

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and compound phrases.
    """
    # Single-word matches: normalized token -> set of ids
    single_word_map = collections.defaultdict(set)
    # Phrase trie root
    root = PhraseTrieNode()

    for phrase, dict_id in dictionary.items():
        phrase = phrase.lower()
        # We'll tokenize phrases on whitespace and on separator runs, but preserve them for boundary detection
        # Here, split into word and separator "tokens"
        tokens = []
        curr = []
        is_curr_word = None

        for c in phrase:
            is_c_word = c.isalnum()
            if is_curr_word is None:
                is_curr_word = is_c_word
                curr = [c]
            elif is_c_word == is_curr_word:
                curr.append(c)
            else:
                tokens.append((''.join(curr), is_curr_word))
                is_curr_word = is_c_word
                curr = [c]
        if curr:
            tokens.append((''.join(curr), is_curr_word))

        # Now flatten into normalized tokens with separator sentinels
        norm_tokens = []
        for s, is_word in tokens:
            if is_word:
                norm_tokens.append(normalize_token(s))
            else:
                norm_tokens.append(_SPECIAL_SEP)
        # Remove consecutive _SPECIAL_SEP (collapse all separator runs)
        cleaned_tokens = []
        for t in norm_tokens:
            if t == _SPECIAL_SEP:
                if not cleaned_tokens or cleaned_tokens[-1] != _SPECIAL_SEP:
                    cleaned_tokens.append(t)
            else:
                cleaned_tokens.append(t)

        # If only a single word, put in single_word_map
        words_only = [token for token in cleaned_tokens if token != _SPECIAL_SEP]
        if len(words_only) == 1 and _SPECIAL_SEP not in cleaned_tokens:
            single_word_map[words_only[0]].add(dict_id)
        # Insert into phrase trie
        node = root
        for t in cleaned_tokens:
            if t not in node.children:
                node.children[t] = PhraseTrieNode()
            node = node.children[t]
        node.dict_ids.add(dict_id)

    # Build index object
    return {"trie_root": root, "single_word_map": single_word_map}

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.
    """
    trie_root = dictionary_index["trie_root"]
    single_word_map = dictionary_index["single_word_map"]

    tokens = list(tokens)
    n = len(tokens)
    # Classify tokens as word or sep
    is_word = [is_word_token(token) for token in tokens]
    normed = [normalize_token(token) for token in tokens]

    # For each token, collect phrase/word dict ids
    annotations = [set() for _ in range(n)]

    # --- Single-word matches
    for i, (tok, is_w) in enumerate(zip(normed, is_word)):
        if is_w and tok in single_word_map:
            annotations[i].update(single_word_map[tok])

    # --- Compound/phrase matching using Trie
    for start in range(n):
        indices_traversed = []
        node = trie_root
        i = start
        last_match_len = None
        last_match_dict_ids = None
        traversed_indices_for_match = None

        j = i
        node_ptr = node
        indices = []
        # We'll need to match alternately words and separators, as encoded in Trie
        # "AAA" <-> word
        # _SPECIAL_SEP <-> separator (may match multiple runs)
        curr_i = i
        node = trie_root
        indices = []
        while curr_i < n:
            # Try to match _SPECIAL_SEP or normed token
            if _SPECIAL_SEP in node.children and not is_word[curr_i]:
                # If expecting a separator, match one or more consecutive separators as ONE _SPECIAL_SEP
                sep_start = curr_i
                while curr_i < n and not is_word[curr_i]:
                    indices.append(curr_i)
                    curr_i += 1
                node = node.children[_SPECIAL_SEP]
                continue
            elif is_word[curr_i] and normed[curr_i] in node.children:
                node = node.children[normed[curr_i]]
                indices.append(curr_i)
                curr_i += 1
            else:
                break
            # After each step, check if current node is terminal for a phrase
            if node.dict_ids:
                # Only match if phrase (at least one word, maybe with separators)
                # Now, mark as "potential" match
                match_indices = list(indices)
                # To conform to requirements, we only annotate *inner* separators.
                # So, for a match covering indices S...E:
                #   - Drop leading/trailing separators from match_indices for phrase boundary
                #   - ANNOTATE all in match_indices EXCEPT drop leading/trailing non-word tokens
                #   - But mark all included in the phrase (including internal separators)
                #   - If the phrase starts or ends with a separator, skip those tokens for annotation
                #   - "AAA", " ", "BBB"  -- match_indices=[0,1,2]  is_word: [T, F, T]  drop 0 if not is_word[0], drop 2 if not is_word[2]
                # Determine indices to annotate: drop leading/trailing indices where is_word is False in match_indices
                first = 0
                last = len(match_indices) - 1
                while first <= last and not is_word[match_indices[first]]:
                    first += 1
                while last >= first and not is_word[match_indices[last]]:
                    last -= 1
                # Only consider as a match if at least one word token remains
                if first <= last:
                    for idx in match_indices[first: last+1]:
                        annotations[idx].update(node.dict_ids)
                    # Internal separators: between first+1 and last-1 (if any)
                    # Requirement: annotate inner separators (between words), but not those outside
                    # But our current loop already does this: all inside match boundary retained, only external ones dropped
                # Continue searching for longer matches after the current match

    # Compose result
    result = []
    for tok, ann in zip(tokens, annotations):
        result.append((tok, set(ann)))
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


