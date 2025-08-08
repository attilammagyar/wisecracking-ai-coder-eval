# --- BEGIN GENERATED CODE ---
import collections.abc
import re

# ---------- Dictionary index (trie) ----------

def _new_trie_node():
    return {"children": {}, "ids": set()}

def _split_words_lower(s: str) -> list[str]:
    # Split on non-alphanumeric, keep only [a-z0-9] tokens, lowercase
    # This makes separator-insensitive matching across arbitrary non-word chars.
    return re.findall(r"[0-9A-Za-z]+", s.lower())

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index (trie) for fast lookup of words and compound phrases.
    Dictionary keys are split into lowercased alphanumeric word tokens.
    """
    root = _new_trie_node()
    for key, val in dictionary.items():
        words = _split_words_lower(key)
        if not words:
            # Ignore entries with no alphanumeric words
            continue
        node = root
        for w in words:
            node = node["children"].setdefault(w, _new_trie_node())
        node["ids"].add(val)
    return root


# ---------- Annotation over token stream ----------

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with dictionary entries matching:
      - Single-word entries (possibly spanning multiple adjacent word tokens without separators)
      - Multi-word phrases across word-runs (with arbitrary separators in-between)
    """
    tokens = list(tokens)
    n = len(tokens)
    # Prepare annotation sets
    ann = [set() for _ in range(n)]

    # Classify tokens into word (alnum) vs separator
    is_word = [t.isalnum() for t in tokens]
    tokens_lower = [t.lower() for t in tokens]

    # Build segments (alternating runs)
    # Each segment is a dict with:
    #   type: 'word' or 'sep'
    #   start: start token index (inclusive)
    #   end: end token index (exclusive)
    #   For word segments: extra fields:
    #       concat: ''.join(lowercased tokens in run)
    #       char_pos: list of cumulative char positions at token boundaries [0, len(t0), len(t0)+len(t1), ...]
    segments = []
    i = 0
    while i < n:
        t_is_word = is_word[i]
        j = i + 1
        while j < n and is_word[j] == t_is_word:
            j += 1
        seg = {"type": "word" if t_is_word else "sep", "start": i, "end": j}
        if t_is_word:
            run_tokens = tokens_lower[i:j]
            concat = "".join(run_tokens)
            char_pos = [0]
            acc = 0
            for rt in run_tokens:
                acc += len(rt)
                char_pos.append(acc)
            seg["concat"] = concat
            seg["char_pos"] = char_pos  # length = number_of_tokens_in_run + 1
            seg["len_tokens"] = j - i
        segments.append(seg)
        i = j

    # Helper: annotate the token indices covered by a match
    def annotate_range(seg_start_idx: int, off_start: int, seg_end_idx: int, off_end: int, ids: collections.abc.Set):
        # Iterate segments from seg_start_idx through seg_end_idx inclusive
        for s_idx in range(seg_start_idx, seg_end_idx + 1):
            seg = segments[s_idx]
            if seg["type"] == "sep":
                # Inner separators between words of the phrase
                for ti in range(seg["start"], seg["end"]):
                    ann[ti].update(ids)
            else:
                # Word segment
                if seg_start_idx == seg_end_idx:
                    # Match within a single word-run
                    a = seg["start"] + off_start
                    b = seg["start"] + off_end
                elif s_idx == seg_start_idx:
                    # First word-run: from off_start to end of run
                    a = seg["start"] + off_start
                    b = seg["end"]
                elif s_idx == seg_end_idx:
                    # Last word-run: from start of run to off_end
                    a = seg["start"]
                    b = seg["start"] + off_end
                else:
                    # Intermediate word-run fully covered
                    a = seg["start"]
                    b = seg["end"]
                for ti in range(a, b):
                    ann[ti].update(ids)

    # DFS through trie starting at a given word-run and token offset
    def extend_from(node, seg_idx: int, offset_in_run: int, start_seg_idx: int, start_offset: int):
        run = segments[seg_idx]
        # Enumerate all possible token-boundary ends within this run
        start_char = run["char_pos"][offset_in_run]
        concat = run["concat"]
        char_pos = run["char_pos"]
        len_tokens = run["len_tokens"]

        # Try all possible e_tok (end token index within the run, exclusive)
        for e_tok in range(offset_in_run + 1, len_tokens + 1):
            end_char = char_pos[e_tok]
            # Substring formed by concatenation of tokens[offset_in_run:e_tok]
            word = concat[start_char:end_char]
            child = node["children"].get(word)
            if child is None:
                continue

            # Record a match ending here (single-word or multi-word at this depth)
            if child["ids"]:
                annotate_range(start_seg_idx, start_offset, seg_idx, e_tok, child["ids"])

            # If we consumed the entire run, we may cross separators to the next word-run
            if e_tok == len_tokens:
                next_seg_idx = seg_idx + 2  # skip the separator-run
                if (
                    seg_idx + 2 < len(segments)
                    and segments[seg_idx + 1]["type"] == "sep"
                    and segments[seg_idx + 2]["type"] == "word"
                ):
                    extend_from(child, next_seg_idx, 0, start_seg_idx, start_offset)

    root = dictionary_index if dictionary_index else _new_trie_node()

    # Start matches at every token boundary inside each word segment
    for s_idx, seg in enumerate(segments):
        if seg["type"] != "word":
            continue
        len_tokens = seg["len_tokens"]
        if len_tokens == 0:
            continue
        for off in range(len_tokens):
            # Optimization: if root has no children, nothing to do
            if not root["children"]:
                break
            extend_from(root, s_idx, off, s_idx, off)

    # Produce final annotated tokens
    annotated_tokens = [(tok, ann_set) for tok, ann_set in zip(tokens, ann)]
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


