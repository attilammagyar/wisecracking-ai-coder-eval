# --- BEGIN GENERATED CODE ---
import collections.abc

# Helper function: is this token a word-like thing?
def is_word(token):
    # You might want to tweak depending on what the app thinks a 'word' is.
    # Here: contains at least one alphanumeric char
    return any(c.isalnum() for c in token)

# Separator marker for Trie construction/walks
SEP = "<SEP>"

class TrieNode:
    __slots__ = ('children', 'entries')
    def __init__(self):
        self.children = {}  # key: str (word or SEP), value: TrieNode
        self.entries = set()

def normalize_token(token):
    return token.lower()

def tokenize_dictionary_phrase(phrase):
    """
    Given a dictionary phrase string, split into alternating [word, sep, word, ...].
    Phrases always start with a word.
    """
    import re
    # Break into [word][sep][word]... sequences.
    tokens = []
    # The regex will find word (-like) segments and separator segments
    for part in re.finditer(r'(\w+)|(\W+)', phrase, re.UNICODE):
        w, s = part.groups()
        if w:
            tokens.append(w.lower())
        else:
            tokens.append(SEP)
    # Remove trailing SEP if present (phrases should end with a word)
    if tokens and tokens[-1] == SEP:
        tokens.pop()
    # Remove leading SEP if present (phrases should start with a word)
    if tokens and tokens[0] == SEP:
        tokens = tokens[1:]
    return tokens

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized Trie for fast phrase/word-lookup.
    Entries at Trie leaves point to the corresponding dictionary IDs for annotation.
    Also includes single word mapping for fast single-token annotation.
    """
    trie = TrieNode()
    word_entries = collections.defaultdict(set)  # normalized_word -> set(entry_id)
    max_phrase_len = 1  # To optimize matching range

    for phrase, entry_id in dictionary.items():
        phrase_tokens = tokenize_dictionary_phrase(phrase)
        # If it's a single word: store as individual word entry also.
        # Because single-word lookup is a common fast path.
        if len(phrase_tokens) == 1 and phrase_tokens[0] != SEP:
            word_entries[phrase_tokens[0]].add(entry_id)
        # Build the Trie for phrase (even single word for uniformity, adds redundancy but safe)
        node = trie
        for t in phrase_tokens:
            if t not in node.children:
                node.children[t] = TrieNode()
            node = node.children[t]
        node.entries.add(entry_id)
        max_phrase_len = max(max_phrase_len, len(phrase_tokens))
    return (trie, word_entries, max_phrase_len)

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object):
    trie, word_entries, max_phrase_len = dictionary_index

    tokens = list(tokens)  # We need index access
    N = len(tokens)
    # For each token, collect sets of annotations
    annotation_sets = [set() for _ in tokens]

    # Fast path: single-word annotations
    for i, token in enumerate(tokens):
        if is_word(token):
            nw = normalize_token(token)
            if nw in word_entries:
                annotation_sets[i].update(word_entries[nw])

    # Annotate phrases (including overlapping/nested ones) using the Trie.
    # For every possible start position, do a Trie walk
    for start in range(N):
        # Only start from a word token
        if not is_word(tokens[start]):
            continue
        # These stacks will hold (trie_node, position, path), where path: list[(token_index, type)]
        # type is 'word' or 'sep'
        queue = [(trie, start, 0, [])]

        while queue:
            node, idx, phrase_idx, match_spans = queue.pop()
            # At phrase_idx == 0 (root), expect word
            pnode = node
            pidx = idx
            path = list(match_spans)

            while True:
                # Figure out next step in phrase
                # Map: phrase alternates between word and SEP.
                # At root or after SEP, expect word.
                # At word node, may have SEP edge: if so, can branch out.

                # Are we at a terminal node? If so, annotate the match.
                if pnode.entries:
                    # Need to annotate inner separator tokens (not leading or trailing)
                    # Our 'path' is list of (token_idx, 'word'|'sep') in order.
                    # Strip leading/trailing separators.
                    first_word = next((i for i, (tid, ttype) in enumerate(path) if ttype == 'word'), 0)
                    last_word = max((i for i, (tid, ttype) in enumerate(path) if ttype == 'word'), default=len(path)-1)
                    # For every token in [first_word, last_word], annotate with phrase
                    involved_tids = []
                    for j, (tid, ttype) in enumerate(path[first_word:last_word+1]):
                        involved_tids.append((tid, ttype))
                    for (tid, ttype) in involved_tids:
                        annotation_sets[tid].update(pnode.entries)
                # Now, continue walking
                cur_idx = pidx
                # Next expected: SEP edge or nothing?
                # If SEP edge: match one or more consecutive separator tokens (cannot be at end/start)
                # If word edge: match a word token
                advanced = False
                # Try SEP edge
                if SEP in pnode.children:
                    # We need at least one separator token starting at cur_idx
                    sep_len = 0
                    while cur_idx < N and not is_word(tokens[cur_idx]):
                        sep_len += 1
                        cur_idx += 1
                    if sep_len > 0:
                        # Found separator sequence
                        # Walk to child node, continue with match
                        child = pnode.children[SEP]
                        # Add ALL separator positions matched, as 'sep' in path
                        ext_path = path + [(tid, 'sep') for tid in range(pidx, pidx+sep_len)]
                        queue.append((child, cur_idx, phrase_idx+1, ext_path))
                        advanced = True
                # Try word edge
                if cur_idx < N and is_word(tokens[cur_idx]):
                    w = normalize_token(tokens[cur_idx])
                    if w in pnode.children:
                        # Walk to word child
                        child = pnode.children[w]
                        queue.append((child, cur_idx+1, phrase_idx+1, path + [(cur_idx, 'word')]))
                        advanced = True
                if not advanced:
                    break  # No more matching possible from here

    # Now bundle up
    for token, anns in zip(tokens, annotation_sets):
        yield (token, anns)
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


