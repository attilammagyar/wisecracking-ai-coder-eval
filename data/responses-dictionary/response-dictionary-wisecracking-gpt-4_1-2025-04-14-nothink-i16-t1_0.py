# --- BEGIN GENERATED CODE ---
import collections.abc

# --- Helper Functions --- #
def is_word_token(token):
    # We'll consider a token to be a 'word' if it has at least one alphanumeric character.
    # That means separators (spaces, punctuation, markdown, etc.) are not 'word' tokens.
    return any(c.isalnum() for c in token)

def normalize_token(token):
    # For matching purposes: normalize to lowercase.
    return token.lower()

def tokenize_dictionary_phrase(phrase):
    """
    Split a dictionary phrase into normalized word/separator token list.
    E.g. "AAA, BBB" -> [("word", "aaa"), ("sep", ","), ("sep", " "), ("word", "bbb")]
    But to keep matching generic, we collapse runs of separators.
    """
    import re
    tokens = []
    current = []
    for c in phrase:
        if c.isalnum():
            current.append(c)
        else:
            if current:
                tokens.append(("word", ''.join(current).lower()))
                current = []
            tokens.append(("sep", c))   # keep separators for now
    if current:
        tokens.append(("word", ''.join(current).lower()))
    # Collapse adjacent separators into single 'sep' for matching flexibility
    res = []
    skipping = False
    for kind, val in tokens:
        if kind == "sep":
            if not skipping:
                res.append(("sep", None))
                skipping = True
        else:
            res.append((kind, val))
            skipping = False
    return res

# --- Trie structure for phrase indexing --- #
class TrieNode:
    __slots__ = ("children", "entries")
    def __init__(self):
        # children: key: ('word', val) or ('sep', None)
        self.children = {}
        self.entries = set()     # set of entry ids for phrases that end here

class DictionaryIndex:
    def __init__(self):
        self.phrase_trie = TrieNode()
        self.max_phrase_len = 1
        self.single_word = collections.defaultdict(set)   # word(token) -> set of entry ids

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    index = DictionaryIndex()
    for key, entry_id in dictionary.items():
        phrase = tokenize_dictionary_phrase(key)
        if not phrase:
            continue # skip empty entries
        # Store max-phrase-length (approx; counts word tokens and sep tokens)
        num_tokens = 1 + sum(1 for tp, _ in phrase if tp == "sep")
        index.max_phrase_len = max(index.max_phrase_len, num_tokens)
        
        # Insert as phrase in trie
        node = index.phrase_trie
        for tp, val in phrase:
            k = (tp, val if tp == "word" else None)
            if k not in node.children:
                node.children[k] = TrieNode()
            node = node.children[k]
        node.entries.add(entry_id)
        # If phrase is a single word, add to single_word mapping
        if (len(phrase) == 1 and phrase[0][0] == "word"):
            index.single_word[phrase[0][1]].add(entry_id)
    return index

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    tokens = list(tokens)
    n = len(tokens)
    annotations = [set() for _ in tokens]   # One set of entry IDs per token
    
    index = dictionary_index
    trie = index.phrase_trie
    
    # Precompute word/separators for all tokens
    token_norm = [normalize_token(tok) for tok in tokens]
    token_is_word = [is_word_token(tok) for tok in tokens]
    
    # Annotate single-word matches
    for i, (tok, isword) in enumerate(zip(token_norm, token_is_word)):
        if isword:
            for entry in index.single_word.get(tok, ()):
                annotations[i].add(entry)

    # Phrase/compound matching (allowing flexible separator matching)
    maxlen = index.max_phrase_len
    for start in range(n):
        positions = []   # list of (token index, type, normed) for matching
        for j in range(start, min(start+maxlen, n)):
            if token_is_word[j]:
                positions.append( ('word', token_norm[j], j) )
            else:
                positions.append( ('sep', None, j) )
        # Now, stepwise traverse trie
        node = trie
        # For each step, store: list of (position in positions, earliest matched token, latest matched token, current TrieNode)
        # Why earliest/latest? So we only annotate inside the matched substring.
        path = []
        pos_idx = 0
        while pos_idx < len(positions):
            tp, val, tok_idx = positions[pos_idx]
            k = (tp, val if tp == "word" else None)
            if k in node.children:
                node = node.children[k]
                path.append(tok_idx)
                # If we ended a phrase, figure out what to annotate
                if node.entries:
                    # Find first/last word in path (ignore leading/trailing sep for annotation)
                    tok_indices = list(path)
                    first, last = 0, len(tok_indices)-1
                    # Skip leading separators
                    while first <= last and not token_is_word[tok_indices[first]]:
                        first += 1
                    # Skip trailing separators
                    while last >= first and not token_is_word[tok_indices[last]]:
                        last -= 1
                    # Annotate all tokens between first and last (inclusive)
                    for idx in range(first, last+1):
                        ti = tok_indices[idx]
                        annotations[ti].update(node.entries)
                    # For the inner tokens, annotate inner separators:
                    # Annotate a separator token only if it is not at the very start or end of the match
                    # (since first/last are always word tokens)
                    # This is handled above; so, inner separators are already included
                    # The requirement is "never the leading or trailing separators", which are first/last
                pos_idx += 1
            elif tp == "sep":
                # In trie, separator is always stored as ('sep', None), so allow to skip over any sep-like tokens in input
                # but only if trie expects a 'sep'
                k2 = ('sep', None)
                if k2 in node.children:
                    node = node.children[k2]
                    path.append(tok_idx)
                    if node.entries:
                        # same logic
                        tok_indices = list(path)
                        first, last = 0, len(tok_indices)-1
                        while first <= last and not token_is_word[tok_indices[first]]:
                            first += 1
                        while last >= first and not token_is_word[tok_indices[last]]:
                            last -= 1
                        for idx in range(first, last+1):
                            ti = tok_indices[idx]
                            annotations[ti].update(node.entries)
                    pos_idx += 1
                else:
                    break # no match
            else:
                break # no match
    # Return as required
    return zip(tokens, annotations)
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


