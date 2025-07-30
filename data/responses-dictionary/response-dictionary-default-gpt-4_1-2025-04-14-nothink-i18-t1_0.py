# --- BEGIN GENERATED CODE ---
import collections.abc
import re

# --- Helper functions ---

def is_word_token(token):
    # Returns True if the token contains at least one alphanumeric character.
    return any(c.isalnum() for c in token)

def tokenize_dictionary_phrase(phrase):
    # Split a dictionary key into alternating word/non-word pieces according to the input tokens
    # E.g., 'AAA, BBB' -> ['aaa', None, 'bbb']
    # Normalize case
    tokens = []
    pos = 0
    while pos < len(phrase):
        # Find longest word run
        m = re.match(r'\w+', phrase[pos:])
        if m:
            tokens.append(phrase[pos:pos+m.end()].lower())
            pos += m.end()
        else:
            # Find longest non-word run
            sep_len = 0
            while pos + sep_len < len(phrase) and not phrase[pos+sep_len].isalnum():
                sep_len += 1
            tokens.append(None)  # Placeholder for any separator, to be matched by any separator token, not concrete value
            pos += sep_len
    # Remove leading or trailing None (separator) slots to correspond to spec
    while tokens and tokens[0] is None:
        tokens.pop(0)
    while tokens and tokens[-1] is None:
        tokens.pop()
    # Collapse multiple Nones (separators) into ONE separator
    result = []
    last_is_none = False
    for t in tokens:
        if t is None:
            if not last_is_none:
                result.append(None)
            last_is_none = True
        else:
            result.append(t)
            last_is_none = False
    return result

# Trie node for phrase matching
class TrieNode:
    __slots__ = ("children", "separator_child", "entry_ids")
    def __init__(self):
        self.children = {}        # word_token (lowercased) -> TrieNode
        self.separator_child = None   # TrieNode for separator slot (None)
        self.entry_ids = set()    # entry ids (meanings) that terminate here

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.
    """
    root = TrieNode()
    for key, entry_id in dictionary.items():
        components = tokenize_dictionary_phrase(key)
        node = root
        for ix, comp in enumerate(components):
            if comp is None:
                if node.separator_child is None:
                    node.separator_child = TrieNode()
                node = node.separator_child
            else:
                comp = comp.lower()
                if comp not in node.children:
                    node.children[comp] = TrieNode()
                node = node.children[comp]
        node.entry_ids.add(entry_id)
    return root

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.
    """
    # Preclassify tokens as word or separator, normalize as needed
    tokens = list(tokens)
    n = len(tokens)
    word_flags = [is_word_token(tok) for tok in tokens]
    token_norms = [tok.lower() if is_word_token(tok) else tok for tok in tokens]

    # For each token, collect annotation ids to a set
    annotations = [set() for _ in range(n)]

    root = dictionary_index

    # For every start position in tokens
    for start in range(n):
        node = root
        pos = start
        matched_token_indices = []  # indices (from start) in tokens that are part of the dictionary phrase
        seg_indices = []  # For recording which indices are separators
        # We only start matching if token at start is a word, or it's the only token (single separator phrase allowed if in dict, but test shows only word starts are relevant)
        # But to match "AAA BBB", test shows separator at start isn't included in match. So we don't start on separators.
        if not word_flags[start]:
            continue

        bfs_states = [ (start, node, []) ]  # (current_pos, current_node, path_indices)
        while bfs_states:
            curr_pos, curr_node, path_indices = bfs_states.pop()
            # If there's an entry id at this node, annotate the correct tokens in path_indices plus curr_pos!
            if curr_node.entry_ids:
                # For phrase_annot_start and phrase_annot_end, remove leading/trailing separators from matched span for annotation
                match_indices = path_indices + [curr_pos] if path_indices else [curr_pos]
                # Find leading and trailing separator runs
                first, last = 0, len(match_indices)-1
                while first <= last and not word_flags[match_indices[first]]:
                    first += 1
                while first <= last and not word_flags[match_indices[last]]:
                    last -= 1
                for idx in range(first, last+1):
                    # Only annotate leading/trailing separators if they are NOT leading/trailing
                    annotations[match_indices[idx]].update(curr_node.entry_ids)
                # For inner separators: only annotate if not leading/trailing in the match
                # Actually, spec says: annotate all tokens in the match span with the entry, except leading/trailing separators.
                # (Implemented by above logic)
            # Try to extend the match
            next_pos = curr_pos + 1
            # If at the end, cannot continue
            if next_pos >= n:
                continue
            # Next token is a separator
            if not word_flags[next_pos]:
                if curr_node.separator_child is not None:
                    # Can take the separator path; advance in tokens (but only one separator at a time:
                    # consecutive separators are separate slots!)
                    bfs_states.append((
                        next_pos,
                        curr_node.separator_child,
                        path_indices + [curr_pos],
                    ))
                # Even if the next is a separator, maybe there could be an entry ending here? (handled above)
                # Also, do not treat separator as matching a word slot (never).
            # Next token is a word
            norm_word = token_norms[next_pos]
            if word_flags[next_pos]:
                if norm_word in curr_node.children:
                    bfs_states.append((
                        next_pos,
                        curr_node.children[norm_word],
                        path_indices + [curr_pos],
                    ))
    # Single-word token annotation (independent of above)
    # (Done via the trie: every phrase, including single-word, is processed by the above. There's no need for a separate pass.)

    # Build the output in the specified tuple format
    annotated_tokens = [ (tok, annotations[ix]) for ix, tok in enumerate(tokens) ]
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


