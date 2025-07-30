# --- BEGIN GENERATED CODE ---
import collections.abc
import re

# ----------------------
# Helper: Token classifier
# ----------------------
def is_word(token):
    # Classifies a token as a 'word', for our annotation policy.
    # A simple policy is alphanumeric tokens (including non-ASCII for robustness).
    # This conservatively treats tokens with at least one alphanumeric character as words.
    # Can adjust as needed for language/dictionary, but this suffices for test cases.
    return any(c.isalnum() for c in token)

# ----------------------
# Helper: Normalization
# ----------------------
def normalize_token(token):
    # Casefolding for case-insensitive comparison
    return token.casefold()

# ----------------------
# Helper: Split phrases into minimal units matching fine-grained tokenization:
# words and non-words (separators).
# Returns a list of tokens, all kept as strings.
def split_phrase(phrase):
    # Use a regular expression that matches "words" (alphanumeric and/or underscore),
    # or non-word sequences (separators).
    # This will separate e.g. "AAA, BBB" into ["AAA", ", ", "BBB"]
    return [tok for tok in re.findall(r"\w+|[^\w]+", phrase)]

# ----------------------
# Trie Node for the phrase trie
# ----------------------
class TrieNode:
    __slots__ = ('children', 'separator', 'entry_ids')
    def __init__(self):
        self.children = dict()    # key: normalized word token, value: TrieNode
        self.separator = None     # key: "_sep", only one for simplicity
        self.entry_ids = set()    # set of dictionary entry ids ending at this node

# ----------------------
# Build dictionary index
# ----------------------

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.
    """
    # 1. Single-token word dictionary: {normalized_word: set(entry_ids)}
    single_word_dict = dict()

    # 2. Compound phrase trie
    trie_root = TrieNode()

    for phrase, entry_id in dictionary.items():
        tokens = split_phrase(phrase)
        # Build for the single-word case
        phrase_word_tokens = [t for t in tokens if is_word(t)]
        if len(phrase_word_tokens) == 1 and len(tokens) == 1:
            # Single word: add to single-word dict
            canonical = normalize_token(tokens[0])
            single_word_dict.setdefault(canonical, set()).add(entry_id)

        # Build the phrase trie
        node = trie_root
        i = 0
        n = len(tokens)
        while i < n:
            token = tokens[i]
            if is_word(token):
                norm_token = normalize_token(token)
                if norm_token not in node.children:
                    node.children[norm_token] = TrieNode()
                node = node.children[norm_token]
                i += 1
            else:
                # For any number of consecutive non-word tokens, consolidate as a single separator
                if node.separator is None:
                    node.separator = TrieNode()
                node = node.separator
                i += 1
        node.entry_ids.add(entry_id)

    return {"root": trie_root, "single_words": single_word_dict}

# ----------------------
# Annotation core
# ----------------------

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.
    """
    tokens = list(tokens)
    n = len(tokens)

    # Pre-classify tokens as word/separator for efficiency
    token_is_word = [is_word(tok) for tok in tokens]
    normalized_tokens = [normalize_token(tok) for tok in tokens]

    # Pull out dictionary index structures
    trie_root = dictionary_index["root"]
    single_word_dict = dictionary_index["single_words"]

    # 1. Start with single-word annotations
    annotations = [set() for _ in range(n)]
    for i, (tok_norm, isword) in enumerate(zip(normalized_tokens, token_is_word)):
        if isword and tok_norm in single_word_dict:
            # Add all entry ids mapped to this word
            annotations[i].update(single_word_dict[tok_norm])

    # 2. Compound phrase matching:
    # For each index, try to find all phrases starting at this position
    # and mark all inner tokens (but not leading/trailing separators)
    for start in range(n):
        i = start
        node = trie_root

        # To match a phrase, alternately walk through word and separator slots.
        # Implementation: at each step, if current token is word, follow children;
        # if separator, follow `separator` pointer.
        traversals = [
            (
                node,   # current trie node
                i,      # current token position in input
                start,  # left-most starting point
                [],     # record of token indexes along this match path
                0,      # count of word tokens matched so far
            )
        ]

        while traversals:
            curr_node, curr_i, match_start, match_path, words_matched = traversals.pop()
            # Save the path position (list index) of each token we touch
            if curr_i >= n:
                continue  # ran off the end, stop
            match_path2 = match_path + [curr_i]

            cur_tok, isword = tokens[curr_i], token_is_word[curr_i]

            # Progression: alternately word -> separator -> word...
            advanced = False
            # At every point, check if this path is an end of a phrase (entry_ids at this node)
            if curr_node.entry_ids:
                # Find span: only annotate word tokens and *inner* separator tokens
                first = match_path2[0]
                last = match_path2[-1]
                # Determine leading + trailing separator indexes to exclude
                l = 0
                while l < len(match_path2) and not token_is_word[match_path2[l]]:
                    l += 1
                r = len(match_path2)
                while r > l and not token_is_word[match_path2[r-1]]:
                    r -= 1
                for idx in match_path2[l:r]:
                    # Only annotate if not a leading or trailing separator
                    if token_is_word[idx] or (l < idx - match_path2[0] < r-1):
                        annotations[idx].update(curr_node.entry_ids)
                    elif not token_is_word[idx]:
                        # Only annotate separators that are not leading/trailing (inner ones)
                        if idx > match_path2[l] and idx < match_path2[r-1]:
                            annotations[idx].update(curr_node.entry_ids)
                # Do not terminate: consider the possibility of phrases nested or overlapping.
                # (E.g., "AAA BBB CCC" and "BBB CCC")

            if isword:
                tok_norm = normalized_tokens[curr_i]
                # Branch: if we can consume a word here, follow it
                if tok_norm in curr_node.children:
                    traversals.append((
                        curr_node.children[tok_norm],
                        curr_i + 1,
                        match_start,
                        match_path2,
                        words_matched + 1,
                    ))
                    advanced = True
            if not isword:
                # Branch: if we can consume a separator here, follow it
                if curr_node.separator is not None:
                    traversals.append((
                        curr_node.separator,
                        curr_i + 1,
                        match_start,
                        match_path2,
                        words_matched,
                    ))
                    advanced = True

            # Terminate if we can't go further
            if not advanced:
                continue

    # Format output as list of (token, set)
    return [(token, annotations[i]) for i, token in enumerate(tokens)]
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


