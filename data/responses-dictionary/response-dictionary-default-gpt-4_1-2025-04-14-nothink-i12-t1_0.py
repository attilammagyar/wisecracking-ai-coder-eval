# --- BEGIN GENERATED CODE ---
import collections.abc
import re

def _normalize_token(token):
    "Return the lower-case token if it's a word, or None if a separator."
    # We define 'word token' as something matching \w+
    if re.match(r"^\w+$", token, re.UNICODE):
        return token.lower()
    else:
        return None

def _tokenize_phrase(phrase):
    "Split dictionary phrase into normalized word tokens (skip separators)."
    # Use \w+ to extract word tokens; ignore separators and spaces
    return tuple(
        token.lower() for token in re.findall(r"\w+", phrase, re.UNICODE)
    )

class _TrieNode:
    __slots__ = ("children", "values")
    def __init__(self):
        self.children = dict()  # key: normalized word token
        self.values = set()     # set of entries reaching this node

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Builds a trie index for fast normalized lookup.
    Each trie branch corresponds to a tuple of normalized word tokens.
    At each node, store annotation set if that prefix is a valid phrase.
    """
    root = _TrieNode()
    # To support single-word entries too, also collect direct word-token lookup
    single_word_map = dict()  # word token -> set(dict values)

    for phrase, value in dictionary.items():
        word_tokens = _tokenize_phrase(phrase)
        if not word_tokens:  # skip meaningless entries
            continue
        # Insert into trie
        node = root
        for word_token in word_tokens:
            if word_token not in node.children:
                node.children[word_token] = _TrieNode()
            node = node.children[word_token]
        node.values.add(value)
        # Also index single-word phrases separately
        if len(word_tokens) == 1:
            single_word_map.setdefault(word_tokens[0], set()).add(value)
    # Return root, and single-word map for quick individual word lookup
    return {"trie": root, "wordmap": single_word_map}

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with all relevant dictionary entries, according to phrase and word matching.
    """
    tokens = list(tokens)
    n = len(tokens)
    trie = dictionary_index["trie"]
    wordmap = dictionary_index["wordmap"]

    # Step 1: Identify which tokens are words and their normalized form
    wordish = []
    for token in tokens:
        norm = _normalize_token(token)
        if norm is not None:
            wordish.append(norm)
        else:
            wordish.append(None)

    # Precompute word-token indices for phrase scans (so we can skip separators as needed)
    word_indices = [i for i, w in enumerate(wordish) if w is not None]

    # For each token, collect annotations (set of values)
    ann = [set() for _ in range(n)]

    # Step 2: Phrase-scanning
    # For every word position, try to match a phrase starting there
    wlen = len(word_indices)
    for wi in range(wlen):
        # Try to extend as far as possible along trie paths starting at word_indices[wi]
        t_indices = []  # Holds all token indices included in current scan (word+sep)
        trie_node = trie
        word_seq_len = 0
        last_matched = None  # (node, end_i, list-of-token-indices)

        # We'll scan from word_indices[wi] onwards, using
        # tokens[j], for j in t_start = word_indices[wi]
        t_start = word_indices[wi]
        ti = t_start
        wi2 = wi
        while wi2 < wlen and trie_node is not None:
            word = wordish[word_indices[wi2]]
            if word in trie_node.children:
                trie_node = trie_node.children[word]
                # Now, from t_start to word_indices[wi2]: the span to be annotated
                t_end = word_indices[wi2]
                # The phrase may cover both word and separator tokens between t_start and t_end.
                t_span = list(range(t_start, t_end+1))
                # Are there inner separators?
                # We want leading/trailing separators excluded from phrase annotation (see below).
                if trie_node.values:
                    # Mark the latest matched phrase (for max. matching, continue further)
                    last_matched = (trie_node, t_span)
                wi2 += 1
            else:
                break

        # Now, for **all** matching phrase lengths found (each prefix in the trie may be a valid phrase),
        # we want to annotate all corresponding tokens as per rules.
        # So, we scan up to the deepest match at each wi. To allow overlapping phrases (as per test_compound_phrase_overlap), 
        # we annotate for **every** phrase match found along the path, not just the deepest.

        # Walk the trie again, and for each prefix that is a valid phrase, process.
        trie_node = trie
        t_span = []
        wi2 = wi
        while wi2 < wlen and trie_node is not None:
            word = wordish[word_indices[wi2]]
            if word in trie_node.children:
                trie_node = trie_node.children[word]
                # Compute the token span covered from word_indices[wi] up to word_indices[wi2]
                t_start = word_indices[wi]
                t_end = word_indices[wi2]
                span = list(range(t_start, t_end+1))
                # At each phrase match (i.e. this trie node has .values), annotate!
                if trie_node.values:
                    # Find inner separator tokens within span
                    # "Leading/trailing" separators = separators before the first word and after the last word
                    # We exclude those; only up to edges of words
                    word_pos = [i for i in span if wordish[i] is not None]
                    if word_pos:
                        first, last = word_pos[0], word_pos[-1]
                        # annotate all tokens in [first, last] inclusive
                        for i in range(first, last+1):
                            # If word token or inner separator (i.e. not first or last AND is a separator)
                            if wordish[i] is not None or (i != first and i != last and wordish[i] is None):
                                ann[i].update(trie_node.values)
                wi2 += 1
            else:
                break

    # Finally, annotate individual word tokens
    for i, w in enumerate(wordish):
        if w is not None and w in wordmap:
            ann[i].update(wordmap[w])

    # Output result
    return [(tokens[i], ann[i]) for i in range(n)]
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


