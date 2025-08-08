# --- BEGIN GENERATED CODE ---
import collections.abc

# ----------------- Helpers -----------------

def _is_word_token(token: str) -> bool:
    # Treat purely alphanumeric tokens as "word" tokens
    return token.isalnum()


def _split_into_words(s: str):
    # Split into maximal runs of alphanumeric characters
    s = s.lower()
    words = []
    i = 0
    n = len(s)
    while i < n:
        # skip non-alnum
        while i < n and not s[i].isalnum():
            i += 1
        if i >= n:
            break
        j = i
        while j < n and s[j].isalnum():
            j += 1
        words.append(s[i:j])
        i = j
    return words


class _TrieNode:
    __slots__ = ("children", "entries")
    def __init__(self):
        self.children = {}  # word(str) -> _TrieNode
        self.entries = set()  # set of entry IDs


def _insert_into_trie(root: _TrieNode, words, entry_id):
    node = root
    for w in words:
        node = node.children.setdefault(w, _TrieNode())
    node.entries.add(entry_id)


# Span data for fast cross-token word matching
class _Span:
    __slots__ = (
        "start", "end", "concat", "boundaries", "boundary_set",
        "offset_of_token", "boundary_to_token_idx"
    )
    def __init__(self, start, end, lower_tokens):
        self.start = start
        self.end = end
        # Build concatenated lowercase string for tokens[start..end]
        parts = []
        boundaries = []
        offset = 0
        offset_of_token = {}
        boundary_to_token_idx = {}
        for idx in range(start, end + 1):
            offset_of_token[idx] = offset
            part = lower_tokens[idx]
            parts.append(part)
            offset += len(part)
            boundaries.append(offset)
            boundary_to_token_idx[offset] = idx
        self.concat = "".join(parts)
        self.boundaries = boundaries  # end offsets after each token
        self.boundary_set = set(boundaries)
        self.offset_of_token = offset_of_token
        self.boundary_to_token_idx = boundary_to_token_idx


# ----------------- Public API -----------------

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized trie index from a dictionary for fast lookup of words and
    compound phrases (insensitive to exact separators, case-insensitive).
    """
    root = _TrieNode()
    entry_len = {}  # entry_id -> number of words in the normalized key

    for key, entry_id in dictionary.items():
        words = _split_into_words(key)
        if not words:
            continue  # nothing to index
        _insert_into_trie(root, words, entry_id)
        entry_len[entry_id] = len(words)

    return {"root": root, "entry_len": entry_len}


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary index.
    """
    tokens = list(tokens)
    n = len(tokens)
    annotated_sets = [set() for _ in range(n)]
    if not tokens:
        return []

    root = dictionary_index["root"]
    entry_len = dictionary_index["entry_len"]

    # Classify tokens and precompute lowercase words
    is_word = [_is_word_token(tok) for tok in tokens]
    lower_tokens = [tok.lower() if is_word[i] else "" for i, tok in enumerate(tokens)]

    # Build word spans
    span_by_token = [None] * n
    spans = []
    i = 0
    while i < n:
        if not is_word[i]:
            i += 1
            continue
        start = i
        j = i
        while j + 1 < n and is_word[j + 1]:
            j += 1
        # We have a span [start, j]
        span = _Span(start, j, lower_tokens)
        spans.append(span)
        for t in range(start, j + 1):
            span_by_token[t] = span
        i = j + 1

    # Quick path: if trie is empty, return empty annotations
    if not root.children and not root.entries:
        return [(tok, annotated_sets[idx]) for idx, tok in enumerate(tokens)]

    # Helper: enumerate child matches (dictionary "word") starting at word token idx
    def iter_child_matches(node: _TrieNode, start_idx: int):
        span = span_by_token[start_idx]
        if span is None:
            return  # start must be a word token
        p = span.offset_of_token[start_idx]
        # For every possible token boundary after p, test substring as candidate child key
        for boundary in span.boundaries:
            if boundary <= p:
                continue
            s = span.concat[p:boundary]
            child = node.children.get(s)
            if child is not None:
                end_idx = span.boundary_to_token_idx[boundary]
                yield child, (start_idx, end_idx)

    # DFS through trie starting at each word token
    from collections import deque

    for start in range(n):
        if not is_word[start]:
            continue

        # Seed with first-level matches from root at 'start'
        stack = deque()
        for child, seg in iter_child_matches(root, start):
            # seg is (start_idx, end_idx) for the first word
            stack.append((child, seg[1], [seg]))  # (node, last_word_end_idx, segments)

            # Handle entries that end after the first word
            if child.entries:
                # segments length is 1 here
                for eid in child.entries:
                    if entry_len.get(eid, 0) == 1:
                        a, b = seg
                        for t in range(a, b + 1):
                            annotated_sets[t].add(eid)

        # Explore longer phrases requiring separators between words
        while stack:
            node, last_end, segments = stack.pop()

            # Try to extend by requiring at least one separator
            sep_start = last_end + 1
            if sep_start >= n or is_word[sep_start]:
                continue  # no separator -> cannot extend

            # Skip one or more separators
            j = sep_start
            while j < n and not is_word[j]:
                j += 1
            if j >= n or not is_word[j]:
                continue  # no next word

            next_word_start = j

            # Try all child matches for the next word
            for child, seg in iter_child_matches(node, next_word_start):
                new_segments = segments + [seg]
                stack.append((child, seg[1], new_segments))

                # If an entry ends here, annotate all its word segments and inner separators
                if child.entries:
                    for eid in child.entries:
                        if entry_len.get(eid, 0) == len(new_segments):
                            # annotate words
                            for a, b in new_segments:
                                for t in range(a, b + 1):
                                    annotated_sets[t].add(eid)
                            # annotate inner separators only
                            for k in range(len(new_segments) - 1):
                                a_prev, b_prev = new_segments[k]
                                a_next, _ = new_segments[k + 1]
                                for t in range(b_prev + 1, a_next):
                                    # these are separators by construction
                                    annotated_sets[t].add(eid)

    # Build result
    annotated_tokens = [(tokens[i], annotated_sets[i]) for i in range(n)]
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


