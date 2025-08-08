# --- BEGIN GENERATED CODE ---
import collections.abc
import re

# Sentinel key for "end of entry" in trie nodes
_END = None

def _is_word_token(tok: str) -> bool:
    # Treat a token as a word iff it's made purely of letters/digits.
    # This matches all tests where words are alphanumerics and separators are not.
    if not tok:
        return False
    # Fast path: avoid scanning twice
    first = tok[0]
    if not first.isalnum():
        return False
    # All chars must be alnum
    return all(c.isalnum() for c in tok)

def _dict_words(key: str):
    # Extract "word units" from a dictionary key: sequences of letters/digits only.
    # Case-insensitive -> lowercased.
    # Example: "AAA, BBB" -> ["aaa", "bbb"]
    return [w.lower() for w in re.findall(r"[0-9A-Za-z]+", key)]

def _trie_insert(trie: dict, seq, entry_id):
    node = trie
    for part in seq:
        node = node.setdefault(part, {})
    node.setdefault(_END, set()).add(entry_id)

def _char_trie_insert(trie: dict, s: str, entry_id):
    node = trie
    for ch in s:
        node = node.setdefault(ch, {})
    node.setdefault(_END, set()).add(entry_id)

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index for fast lookup.
    - word_to_ids: direct single-word lookup (case-insensitive)
    - phrase_trie: trie over sequences of 2+ words (word units)
    - single_trie: character trie over single-unit entries (to match concatenations across tokens)
    """
    word_to_ids = {}  # dict[str, set]
    phrase_trie = {}  # nested dict
    single_trie = {}  # char trie for single-unit entries (lowercased)

    for key, entry_id in dictionary.items():
        units = _dict_words(key)
        if not units:
            continue
        if len(units) == 1:
            w = units[0]
            word_to_ids.setdefault(w, set()).add(entry_id)
            # Single-unit entries go into char trie as well for concatenated matches
            _char_trie_insert(single_trie, w, entry_id)
        else:
            # Multi-word phrases (2+ units) go into the phrase trie
            _trie_insert(phrase_trie, units, entry_id)

    return {
        "word_to_ids": word_to_ids,
        "phrase_trie": phrase_trie,
        "single_trie": single_trie,
    }

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    tokens = list(tokens)
    n = len(tokens)
    # Preprocess tokens
    is_word = [_is_word_token(t) for t in tokens]
    lc_token = [t.lower() if w else t for t, w in zip(tokens, is_word)]

    # Prepare output annotations
    ann = [set() for _ in range(n)]

    word_to_ids = dictionary_index["word_to_ids"]
    phrase_trie = dictionary_index["phrase_trie"]
    single_trie = dictionary_index["single_trie"]

    # 1) Direct single-word annotations (case-insensitive)
    for i in range(n):
        if is_word[i]:
            ids = word_to_ids.get(lc_token[i])
            if ids:
                ann[i].update(ids)

    # 2) Multi-word phrase matching (2+ units), annotate inner separators too.
    #    For each start word index s, walk the trie across next words separated by >=1 non-word tokens.
    for s in range(n):
        if not is_word[s]:
            continue
        first = lc_token[s]
        node = phrase_trie.get(first)
        if not node:
            continue

        # We'll expand match by hopping word->(one or more seps)->word->...
        cover_indices = [s]  # indices to annotate if/when we hit an end
        cur_node = node
        prev_idx = s

        # Repeatedly find the next word with >=1 separator in between
        while True:
            j = prev_idx + 1
            had_sep = False
            # Collect inner separators (must have at least one)
            while j < n and not is_word[j]:
                had_sep = True
                j += 1
            if not had_sep or j >= n or not is_word[j]:
                break  # need >=1 separator then a word
            next_word = lc_token[j]
            child = cur_node.get(next_word)
            if not child:
                break

            # Extend cover: add all separators between prev_idx and j, then j itself
            cover_indices.extend(range(prev_idx + 1, j))
            cover_indices.append(j)

            cur_node = child
            prev_idx = j

            # If we hit a phrase end, annotate all covered indices so far
            end_ids = cur_node.get(_END)
            if end_ids:
                for k in cover_indices:
                    ann[k].update(end_ids)

        # Done expanding from start s

    # 3) Concatenated single-unit matches across runs of adjacent word tokens (no separators).
    #    Use the character trie. Enforce matches start and end at token boundaries only.
    i = 0
    while i < n:
        if not is_word[i]:
            i += 1
            continue
        # Identify a maximal run [run_start, run_end] of consecutive word tokens
        run_start = i
        j = i
        while j < n and is_word[j]:
            j += 1
        run_end = j - 1
        # Scan all starts within the run
        for s in range(run_start, run_end + 1):
            # Early exit: if the first char isn't present, skip
            tok_s = lc_token[s]
            if not tok_s:
                continue
            node = single_trie.get(tok_s[0])
            if not node:
                continue
            # Consume the rest of token s
            # We already consumed first char to move into 'node'
            for ch in tok_s[1:]:
                node = node.get(ch)
                if node is None:
                    break
            else:
                # Entire token s consumed: check end here (match must end at token boundary)
                end_ids = node.get(_END)
                if end_ids:
                    ann[s].update(end_ids)
                # Try to extend across further tokens in the run
                stop_outer = False
                for e in range(s + 1, run_end + 1):
                    tok = lc_token[e]
                    for ch in tok:
                        node = node.get(ch)
                        if node is None:
                            stop_outer = True
                            break
                    if stop_outer:
                        break
                    end_ids = node.get(_END)
                    if end_ids:
                        # Annotate the full token span [s..e]
                        for k in range(s, e + 1):
                            ann[k].update(end_ids)
            # Continue with next start s
        i = run_end + 1

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


