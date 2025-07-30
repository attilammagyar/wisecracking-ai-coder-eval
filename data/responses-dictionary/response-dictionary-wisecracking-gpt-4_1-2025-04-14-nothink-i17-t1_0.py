# --- BEGIN GENERATED CODE ---
import collections.abc
import string

def _is_word_token(token):
    # Consider as word if at least one alnum and not just punctuation/space/markdown
    return any(c.isalnum() for c in token)

def _normalize_token(token):
    # Lowercase, remove extra spaces, treat markdown/punct as is
    return token.lower()

def _split_phrase_to_chunks(phrase):
    """
    Splits a phrase string from the dictionary into alternating word/separator chunks.
    Example: "AAA, BBB" -> ["aaa", ", ", "bbb"]
    """
    import re
    s = phrase.lower()
    # Match sequences of word chars (\w+), or non-word chars (\W+)
    pattern = r'(\w+|\W+)'
    chunks = [chunk for chunk in re.findall(pattern, s) if chunk.strip() != "" or not chunk.strip()]
    return chunks

class TrieNode:
    __slots__ = ['children', 'entry_ids', 'is_word']

    def __init__(self, is_word):
        self.children = {}    # key: normalized token, value: TrieNode
        self.entry_ids = set()
        self.is_word = is_word  # True if node expects a word-token next, else separator

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build normalized (case-insensitive, separator-insensitive) phrase trie.
    """
    root = TrieNode(is_word=None)  # root doesn't care
    # Map for fast single word lookups! { normalized: set(entry_ids) }
    word_index = collections.defaultdict(set)
    max_phrase_len = 1

    for phrase, entry_id in dictionary.items():
        chunks = _split_phrase_to_chunks(phrase)
        if not chunks:
            continue
        max_phrase_len = max(max_phrase_len, len(chunks))
        n_chunks = len(chunks)
        node = root
        # Track expected alternation: Start expects word if first chunk is word
        for i, chunk in enumerate(chunks):
            is_word = _is_word_token(chunk)
            key = chunk if is_word else chunk  # case-insensitive handled already
            if key not in node.children:
                node.children[key] = TrieNode(is_word)
            node = node.children[key]
        node.entry_ids.add(entry_id)
        # Add to word index if the phrase is a single word
        if len(chunks) == 1 and _is_word_token(chunks[0]):
            word_index[chunks[0]].add(entry_id)

    root.word_index = word_index  # attach for fast word-only lookups
    root.max_phrase_len = max_phrase_len
    return root

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary (compounds and singles).
    """
    tokens = list(tokens)
    N = len(tokens)
    annotations = [set() for _ in range(N)]
    trie = dictionary_index
    max_len = getattr(trie, "max_phrase_len", 5)

    # Normalize tokens and classify as word/separator
    norm_tokens = [(_normalize_token(tok), _is_word_token(tok)) for tok in tokens]

    # Fast single word annotation
    word_index = getattr(trie, "word_index", {})

    for i, (ntok, is_word) in enumerate(norm_tokens):
        if is_word and ntok in word_index:
            annotations[i].update(word_index[ntok])

    # Compound phrase annotation using the trie
    for start in range(N):
        nodes = [(trie, start, -1)]  # (node, pos, last_matched_entry_span_end)
        # Explore trie from current position. Multi-path because of separators.
        while nodes:
            node, pos, last_match = nodes.pop()
            if pos >= N:
                continue
            ntok, is_word = norm_tokens[pos]
            # At root, can accept any branch ("AAA" or " " etc)
            for label, child in node.children.items():
                expect_word = child.is_word
                # Only allow matching word-to-word, sep-to-sep.
                if expect_word and is_word and label == ntok:
                    # Word match
                    next_pos = pos + 1
                    # On match, check for entry_id(s)
                    if child.entry_ids:
                        # Find span: go back to start, mark positions for annotation,
                        # But as per requirements, only annotate internal separators
                        span = (start, next_pos)
                        # Annotate tokens in the span:
                        #   - If length > 1: annotate all, but never first/last if they are separators
                        #   - If length == 1: annotate the only token
                        idx0, idxN = span[0], span[1]
                        sel = list(range(idx0, idxN))  # tokens in phrase
                        if len(sel) == 1:
                            sel_indices = sel
                        else:
                            sel_indices = sel
                            # Remove leading sep
                            if not norm_tokens[sel[0]][1]:
                                sel_indices = sel_indices[1:]
                            # Remove trailing sep
                            if sel_indices and not norm_tokens[sel_indices[-1]][1]:
                                sel_indices = sel_indices[:-1]
                        for j in sel_indices:
                            annotations[j].update(child.entry_ids)
                    # Keep matching longer phrases
                    nodes.append((child, next_pos, last_match))
                elif not expect_word and not is_word and label == ntok:
                    # Separator match
                    next_pos = pos + 1
                    if child.entry_ids:
                        # Same span logic as above
                        span = (start, next_pos)
                        sel = list(range(span[0], span[1]))
                        if len(sel) == 1:
                            sel_indices = sel
                        else:
                            sel_indices = sel
                            if not norm_tokens[sel[0]][1]:
                                sel_indices = sel_indices[1:]
                            if sel_indices and not norm_tokens[sel_indices[-1]][1]:
                                sel_indices = sel_indices[:-1]
                        for j in sel_indices:
                            annotations[j].update(child.entry_ids)
                    nodes.append((child, next_pos, last_match))
    # Build output.
    return [(tokens[i], annotations[i]) for i in range(N)]
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


