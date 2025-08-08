# --- BEGIN GENERATED CODE ---
import collections.abc

def _split_alnum_words(s: str):
    """
    Split a string into lowercased alnum 'words' (runs of [A-Za-z0-9]+),
    ignoring punctuation and whitespace.
    """
    out = []
    buf = []
    for ch in s:
        if ch.isalnum():
            buf.append(ch.lower())
        else:
            if buf:
                out.append(''.join(buf))
                buf = []
    if buf:
        out.append(''.join(buf))
    return out


def _insert_char_trie(trie: dict, word: str, value):
    node = trie
    for ch in word:
        node = node.setdefault(ch, {})
    ids = node.get('_ids')
    if ids is None:
        node['_ids'] = {value}
    else:
        ids.add(value)


def _insert_word_trie(trie: dict, words: list[str], value):
    node = trie
    for w in words:
        node = node.setdefault(w, {})
    ids = node.get('_ids')
    if ids is None:
        node['_ids'] = {value}
    else:
        ids.add(value)


def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.

    Parameters:
        dictionary: Mapping strings (keys) to meanings (values).
    """
    word_char_trie = {}
    phrase_word_trie = {}
    # Optional fast path for exact single-word tokens
    single_word_map = {}

    for key, val in dictionary.items():
        words = _split_alnum_words(key)
        if not words:
            continue
        if len(words) == 1:
            w = words[0]
            _insert_char_trie(word_char_trie, w, val)
            s = single_word_map.get(w)
            if s is None:
                single_word_map[w] = {val}
            else:
                s.add(val)
        else:
            _insert_word_trie(phrase_word_trie, words, val)

    return {
        'word_char_trie': word_char_trie,     # single-word entries, char trie
        'phrase_word_trie': phrase_word_trie, # multi-word phrases, word trie
        'single_word_map': single_word_map,   # exact token -> ids (lowercased)
    }


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.

    Parameters:
        dictionary_index:   A dictionary index created by build_dictionary_index()
        tokens:             The tokens to be annotated.

    Return:
        annotated_tokens:   A list containing (token, annotations) pairs for each token in tokens.
    """
    tok_list = list(tokens)
    n = len(tok_list)
    if n == 0:
        return []

    # Prepare helpers
    is_word = [t.isalnum() for t in tok_list]
    lower = [t.lower() for t in tok_list]

    ann = [set() for _ in range(n)]

    word_char_trie = dictionary_index.get('word_char_trie', {})
    phrase_word_trie = dictionary_index.get('phrase_word_trie', {})
    single_word_map = dictionary_index.get('single_word_map', {})

    # 1) Exact single-token matches (fast path)
    if single_word_map:
        for i in range(n):
            if is_word[i]:
                ids = single_word_map.get(lower[i])
                if ids:
                    ann[i].update(ids)

    # 2) Single-word entries matched across runs of adjacent word tokens (no separators)
    #    Use the character trie, and only accept matches at token boundaries.
    if word_char_trie:
        i = 0
        while i < n:
            if not is_word[i]:
                i += 1
                continue
            run_start = i
            while i < n and is_word[i]:
                i += 1
            run_end = i - 1

            # Scan from every start within this run
            for s in range(run_start, run_end + 1):
                node = word_char_trie
                dead = False
                for e in range(s, run_end + 1):
                    # Walk characters of token e
                    for ch in lower[e]:
                        node = node.get(ch)
                        if node is None:
                            dead = True
                            break
                    if dead:
                        break
                    ids = node.get('_ids')
                    if ids:
                        # Annotate tokens s..e inclusive
                        for k in range(s, e + 1):
                            ann[k].update(ids)

    # 3) Multi-word phrases (require at least one separator token between successive words)
    if phrase_word_trie:
        word_positions = [idx for idx, wflag in enumerate(is_word) if wflag]
        word_values = [lower[idx] for idx in word_positions]
        W = len(word_positions)

        for a in range(W):
            node = phrase_word_trie.get(word_values[a])
            if node is None:
                continue

            # Try to extend a phrase starting at word_positions[a]
            prev_tok_idx = word_positions[a]

            # It’s conceivable (though not in our tests) to have a 1-word phrase stored;
            # handle generically:
            ids = node.get('_ids')
            if ids:
                # Annotate tokens from first to first (only the word token)
                k0 = prev_tok_idx
                ann[k0].update(ids)

            j = a + 1
            while j < W:
                curr_tok_idx = word_positions[j]
                # Must have at least one separator token between words in a phrase:
                if curr_tok_idx - prev_tok_idx <= 1:
                    break

                node = node.get(word_values[j])
                if node is None:
                    break

                ids = node.get('_ids')
                if ids:
                    # Annotate from first word token to current word token inclusive;
                    # this includes only inner separators, never leading/trailing.
                    start_tok = word_positions[a]
                    end_tok = curr_tok_idx
                    for k in range(start_tok, end_tok + 1):
                        ann[k].update(ids)

                prev_tok_idx = curr_tok_idx
                j += 1

    return [(tok_list[i], ann[i]) for i in range(n)]
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


