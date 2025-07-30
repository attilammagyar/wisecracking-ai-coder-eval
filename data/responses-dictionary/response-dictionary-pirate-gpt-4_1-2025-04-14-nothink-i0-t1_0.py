# --- BEGIN GENERATED CODE ---
import collections.abc

def _normalize_token(token):
    return token.lower()

def _is_word(token):
    # A "word" token must contain at least one alph' or digit, else be a separator.
    return any(c.isalnum() for c in token)

def _tokenize_phrase(phrase):
    # Split the phrase into an alternatin' list o' word and separator tokens,
    # so we can build our trie in the same structure as the stream o' tokens
    tokens = []
    curr = ''
    # We'll group consecutive word/non-word chars the same way as token splitting,
    phrase = phrase.strip()
    i = 0
    while i < len(phrase):
        c = phrase[i]
        if c.isspace():
            # whitespace is a separator token; gobble it up as a single token
            if curr:
                tokens.append(curr)
                curr = ''
            ws = c
            i += 1
            while i < len(phrase) and phrase[i].isspace():
                ws += phrase[i]
                i += 1
            tokens.append(ws)
        elif c.isalnum():
            # Build up a word
            if curr and not curr[0].isalnum():
                tokens.append(curr)
                curr = ''
            curr += c
            i += 1
        else:
            # Punctuation/other, treat each as its own separator token
            if curr:
                tokens.append(curr)
                curr = ''
            tokens.append(c)
            i += 1
    if curr:
        tokens.append(curr)
    return [_normalize_token(t) for t in tokens if t]

class TrieNode:
    __slots__ = ['children', 'dict_entry_ids']
    def __init__(self):
        self.children = {}  # token(str) -> TrieNode
        self.dict_entry_ids = set()  # Set of IDs for phrases ending here

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    # We'll return a structure:
    # {
    #   'trie': trie root node,
    #   'single_word': { token: set(ids) },  # for individual word lookup
    #   'max_phrase_len': maximum number of tokens in any phrase (for speed)
    # }
    trie = TrieNode()
    single_word = collections.defaultdict(set)
    max_phrase_tokens = 1
    for phrase, entry_id in dictionary.items():
        tokens = _tokenize_phrase(phrase)
        if not tokens:
            continue
        # Mark max phrase length for optimization
        max_phrase_tokens = max(max_phrase_tokens, len(tokens))
        # phrase as single dictionary entry
        if len(tokens) == 1 and _is_word(tokens[0]):
            single_word[tokens[0]].add(entry_id)
        # Add to trie for compound/multi-token match
        node = trie
        for tok in tokens:
            if tok not in node.children:
                node.children[tok] = TrieNode()
            node = node.children[tok]
        node.dict_entry_ids.add(entry_id)
    #
    return {'trie': trie, 'single_word': {k: set(v) for k, v in single_word.items()}, 'max_phrase_len': max_phrase_tokens}

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    # Prepare
    tokens = list(tokens)
    n = len(tokens)
    annotations = [set() for _ in tokens]
    norm_tokens = [_normalize_token(tok) for tok in tokens]
    is_word = [_is_word(tok) for tok in tokens]
    single_word_table = dictionary_index['single_word']
    trie = dictionary_index['trie']
    max_phrase_len = dictionary_index['max_phrase_len']

    # 1. Annotate single-token dictionary entries
    for idx, (token, norm, wordlike) in enumerate(zip(tokens, norm_tokens, is_word)):
        if wordlike and norm in single_word_table:
            annotations[idx].update(single_word_table[norm])

    # 2. Try to match all compound phrases (arrrrr)
    for start in range(n):
        # Skip separators at start, since phrase must start with word token
        if not is_word[start]:
            continue
        node = trie
        tpos = start
        # We'll walk the trie and token list in tandem, allowin' separators interleaved as needed
        # For each walk, keep track of all potential phrase end-points and the involved token indices
        phrase_tokens = []
        last_match = None  # (end_idx_inclusive (int), set(dict_entry_ids))
        while tpos < n:
            norm_tok = norm_tokens[tpos]
            tok = norm_tok
            # Word or separator, we step down the trie if matches.
            if tok in node.children:
                node = node.children[tok]
                phrase_tokens.append(tpos)
                if node.dict_entry_ids:
                    # Update last match: always include from start..tpos (inclusive)
                    last_match = (tpos, set(node.dict_entry_ids))
                tpos += 1
            else:
                # If we've just passed a word, and next tokens are separators, skip them (as part of phrase per the rules),
                # but only the *inner* ones between words!
                if not is_word[tpos]:
                    # Accept the separator; if trie doesn't branch on this token, break -
                    # so, the separator must be in the phrase entry as well to continue
                    if tok in node.children:
                        node = node.children[tok]
                        phrase_tokens.append(tpos)
                        if node.dict_entry_ids:
                            last_match = (tpos, set(node.dict_entry_ids))
                        tpos += 1
                    else:
                        break
                else:
                    break  # no match can continue if this word token doesn't match next trie node
            # Optimization: Do not look beyond the max phrase length
            if len(phrase_tokens) >= max_phrase_len:
                break

        # If a phrase matched, annotate the involved tokens (be careful: only inner separators)
        if last_match:
            end, entry_ids = last_match  # end is inclusive
            phrase_range = range(start, end + 1)
            # Only annotate tokens, but not any leading/trailing separators.
            # If separators at ends, skip 'em.
            first = phrase_range.start
            last = phrase_range.stop - 1
            # Find actual first & last word tokens in the matched seq
            inner_start = first
            while inner_start <= last and not is_word[inner_start]:
                inner_start += 1
            inner_end = last
            while inner_end >= inner_start and not is_word[inner_end]:
                inner_end -= 1
            # Now, annotate all tokens from inner_start .. inner_end (including inner separators),
            # but not leading or trailing separators.
            for idx in range(inner_start, inner_end + 1):
                annotations[idx].update(entry_ids)
            # Caution: If there be only one word, annotate it (special case)
            # All handled by above if inner_start == inner_end
            # We do NOT skip to last+1 since overlapping matches be required!

    # Final result
    return [(tok, ann) for tok, ann in zip(tokens, annotations)]
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


