# --- BEGIN GENERATED CODE ---
import collections.abc

def _is_word(token):
    # A word token is defined as anything with at least 1 alphanumeric character
    return any(c.isalnum() for c in token)

def _normalize_token(token):
    # Lower-case for case-insensitivity
    return token.lower()

def _split_dictionary_phrase(phrase):
    """
    Split a dictionary phrase into a list of ('word', token) or ('sep', sep-str) parts.
    E.g. "Hello, world!" -> [('word', 'hello'), ('sep', ','), ('word', 'world'), ('sep', '!')]
    Separators are anything not containing isalnum.
    """
    out = []
    part = []
    prev_is_word = None
    for c in phrase:
        is_word = c.isalnum()
        if prev_is_word is None:
            prev_is_word = is_word
        if is_word == prev_is_word:
            part.append(c)
        else:
            chunk = ''.join(part)
            if prev_is_word:
                out.append(('word', _normalize_token(chunk)))
            else:
                out.append(('sep', chunk))
            part = [c]
            prev_is_word = is_word
    if part:
        chunk = ''.join(part)
        if prev_is_word:
            out.append(('word', _normalize_token(chunk)))
        else:
            out.append(('sep', chunk))
    return out

class TrieNode:
    __slots__ = ('children_word', 'children_sep', 'values', 'is_terminal')
    def __init__(self):
        self.children_word = {}  # token -> TrieNode
        self.children_sep = {}   # normalized sep (not used in matching) for data structure completeness
        self.values = set()
        self.is_terminal = False

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    # Build a trie for phrase matching, and a direct map for single word lookup
    root = TrieNode()
    single_word_map = {}  # normalized token -> set(ids)
    # Also store the maximum dictionary entry phrase length in terms of 'word' tokens
    max_phrase_words = 1

    for phrase, value in dictionary.items():
        parts = _split_dictionary_phrase(phrase)
        cur = root
        word_count = 0
        for idx, (kind, tok) in enumerate(parts):
            if kind == 'word':
                norm_tok = _normalize_token(tok)
                word_count += 1
                if norm_tok not in cur.children_word:
                    cur.children_word[norm_tok] = TrieNode()
                cur = cur.children_word[norm_tok]
            else:  # 'sep'
                # We don't care about the concrete value of the separator at this level;
                # treat any run of separators as a transition.
                # For completeness, store sep transitions, though we will match loosely.
                if None not in cur.children_sep:
                    cur.children_sep[None] = TrieNode()
                cur = cur.children_sep[None]
        cur.values.add(value)
        cur.is_terminal = True
        if word_count == 1:
            # Track single word dictionary entry for fast lookup
            norm_tok = _normalize_token(parts[0][1])
            single_word_map.setdefault(norm_tok, set()).add(value)
        if word_count > max_phrase_words:
            max_phrase_words = word_count

    # Bundle up in index object
    idx = {
        'trie': root,
        'single_word_map': single_word_map,
        'max_phrase_words': max_phrase_words,
    }
    return idx

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    tokens = list(tokens)
    N = len(tokens)
    annotations = [set() for _ in tokens]
    trie = dictionary_index['trie']
    single_word_map = dictionary_index['single_word_map']
    max_phrase_words = dictionary_index['max_phrase_words']

    # Precompute which tokens are word tokens
    is_word = [_is_word(tok) for tok in tokens]
    norm_tokens = [_normalize_token(tok) for tok in tokens]

    # First, annotate all single-word tokens if present in dictionary
    for i, (tok, word_flag) in enumerate(zip(norm_tokens, is_word)):
        if word_flag and tok in single_word_map:
            annotations[i].update(single_word_map[tok])

    # For efficiency, try each position as the start of a compound phrase
    for start in range(N):
        # Only allow phrases starting at a word token
        if not is_word[start]:
            continue
        i = start
        node = trie
        idx = start
        # phrase_parts: alternate between word tokens and separator runs
        indices = [start]  # All token indices involved in the phrase so far
        word_count = 1
        while idx < N:
            # Check at this point if we have a terminal in the Trie (i.e., matched a phrase)
            if node.is_terminal:
                # Find boundaries: phrase = tokens[start:idx]
                # Only annotate leading/trailing separators if they were part of a dictionary phrase
                # But by conventions of the matching: phrases do not start/end with non-word
                # Only the *inner* separators are annotated
                # So, annotate each tokens between start and idx (inclusive of both)
                # But for outer tokens: if it's a separator and it's the first/last, skip
                # Solution: gather involved token indices:
                indices_set = set(indices)
                # For phrase of length 1: only the word itself (no leading/trailing separators)
                if len(indices_set) == 1:
                    for t in indices_set:
                        annotations[t].update(node.values)
                else:
                    # For multi-word phrase, annotate all except leading/trailing separators (if any)
                    # So, for each token index from indices, skip if at boundaries and not a word token
                    for pos, t in enumerate(indices):
                        if pos == 0 or pos == len(indices) - 1:
                            if not is_word[t]:
                                continue  # skip leading/trailing separator
                        annotations[t].update(node.values)
            # Now, try to extend
            # Next: either a separator run (one or more non-word), or a word
            # If we just consumed a word, next must be a separator
            ptr = idx
            # Look for a run of one or more separators (if possible in trie)
            while ptr+1 < N and not is_word[ptr+1]:
                ptr += 1
            if ptr > idx:
                # At least one separator
                if None in node.children_sep:
                    # We can step over one or more non-word tokens as separator
                    # All are included in phrase (for inner separator annotation)
                    node_sep = node.children_sep[None]
                    # Next, expect a word token
                    if ptr+1 < N and is_word[ptr+1]:
                        next_tok = norm_tokens[ptr+1]
                        if next_tok in node_sep.children_word:
                            # Step to next word node
                            node_word = node_sep.children_word[next_tok]
                            # Track involved tokens: from current idx+1 up to ptr+1 (separator run), then the word
                            phrase_indices = indices + list(range(idx+1, ptr+2))
                            indices = phrase_indices
                            idx = ptr+1
                            node = node_word
                            word_count += 1
                            continue
                # Either no separator edge, or can't proceed
                break
            # If no separator(s), try to follow a word token directly next (for joined words, eg 'AAABBB')
            if idx+1 < N and is_word[idx+1]:
                next_tok = norm_tokens[idx+1]
                if next_tok in node.children_word:
                    node = node.children_word[next_tok]
                    indices.append(idx+1)
                    idx += 1
                    word_count += 1
                    continue
            break  # can't match further

        # Don't look for phrases starting at a non-word token

    # Output
    return [(tok, annotations[i]) for i, tok in enumerate(tokens)]
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


