# --- BEGIN GENERATED CODE ---
None
# --- END GENERATED CODE ---

import unittest


class TestParser(unittest.TestCase):
    maxDiff = None

    def test_empty(self):
        self.assert_parsed(
            "",
            {
                "stanzas": [],
                "width": 1280,
                "height": 720,
                "background": Style.GREEN,
                "fps": 30,
                "last_frame": 0,
            }
        )

    def test_invalid_syntax(self):
        self.assertRaises(InvalidCommand, self.parse, "{}")
        self.assertRaises(InvalidCommand, self.parse, "{,}")
        self.assertRaises(InvalidCommand, self.parse, "{,note}")
        self.assertRaises(InvalidCommand, self.parse, "{z,note}")
        self.assertRaises(InvalidCommand, self.parse, "{-2,note}")
        self.assertRaises(InvalidCommand, self.parse, "{0/0,note}")
        self.assertRaises(InvalidCommand, self.parse, "{invalid command}")
        self.assertRaises(InvalidInteger, self.parse, "{FPS=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{FPS=0}")
        self.assertRaises(InvalidInteger, self.parse, "{BPM=0}")
        self.assertRaises(InvalidInteger, self.parse, "{BPM=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{WIDTH=0}")
        self.assertRaises(InvalidInteger, self.parse, "{HEIGHT=0}")
        self.assertRaises(InvalidInteger, self.parse, "{WIDTH=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{HEIGHT=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{TEXT_SIZE=0}")
        self.assertRaises(InvalidInteger, self.parse, "{RUBY_SIZE=0}")
        self.assertRaises(InvalidInteger, self.parse, "{TEXT_SIZE=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{RUBY_SIZE=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{LINE_DISTANCE=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{RUBY_DISTANCE=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{BORDER_WIDTH=-1}")
        self.assertRaises(InvalidInteger, self.parse, "{DOT_SIZE=-1}")
        self.assertRaises(UnknownSetting, self.parse, "{UNKNOWN_SETTING=42}")
        self.assertRaises(InvalidColor, self.parse, "{BACKGROUND=#zzzzzz}")

    def test_global_settings_are_overwritten(self):
        self.assert_parsed(
"""\
{FPS=29}
{BACKGROUND=#000000}
{WIDTH=800}
{HEIGHT=600}
{LINE_DISTANCE=2}

{FPS=24}
{BACKGROUND=#0000ff}
{WIDTH=640}
{HEIGHT=480}
{LINE_DISTANCE=10}
""",
            {
                "stanzas": [],
                "width": 640,
                "height": 480,
                "background": (0, 0, 255),
                "fps": 24,
                "last_frame": 0,
            }
        )

    def test_global_settings_must_be_set_before_first_note(self):
        self.assertRaises(
            GlobalSettingsMustBeSpecifiedBeforeFirstNote,
            self.parse,
            "{1,note}{FPS=42}"
        )
        self.assertRaises(
            GlobalSettingsMustBeSpecifiedBeforeFirstNote,
            self.parse,
            "{1,note}{WIDTH=800}"
        )
        self.assertRaises(
            GlobalSettingsMustBeSpecifiedBeforeFirstNote,
            self.parse,
            "{1,note}{HEIGHT=600}"
        )
        self.assertRaises(
            GlobalSettingsMustBeSpecifiedBeforeFirstNote,
            self.parse,
            "{1,note}{LINE_DISTANCE=42}"
        )
        self.assertRaises(
            GlobalSettingsMustBeSpecifiedBeforeFirstNote,
            self.parse,
            "{1,note}{BACKGROUND=#000000}"
        )

    def test_stanzas_and_lines_without_notes_and_whitespace_are_ignored(self):
        lyrics = self.parse(
"""


            {1,stanza1-line1-note1}        {1,stanza1-line1-note2}
                {BPM=140}
  \t        {1,stanza1-line2-note1}  {1,stanza1-line2-note2}



            {1,stanza2-line2-note1}

"""
        )
        self.assertEqual(
"""\
stanza1-line1-note1 stanza1-line1-note2
stanza1-line2-note1 stanza1-line2-note2

stanza2-line2-note1
""",
            self.lyrics_to_str(lyrics)
        )

    def test_one_line_of_lyrics_can_be_multiple_source_lines_using_backslash(self):
        lyrics = self.parse(
"""
{1,s1-l1-n1}{1,s1-l1-n2}\\
    {1,s1-l1-n3}

{1,s2-l1-n1}{1,s2-l1-n2}\\
  {1,s2-l1-n3}
{1,s2-l2-n1}{1,s2-l2-n2}\\

{1,s3-l1-n1}{1,s3-l1-n2}\\"""
        )
        self.assertEqual(
"""\
s1-l1-n1 s1-l1-n2 s1-l1-n3

s2-l1-n1 s2-l1-n2 s2-l1-n3
s2-l2-n1 s2-l2-n2

s3-l1-n1 s3-l1-n2
""",
            self.lyrics_to_str(lyrics)
        )

    def test_comma_is_allowed_in_lyrics(self):
        lyrics = self.parse("{1/8,what comes next, is a comma:}{1/8,,}")
        self.assertEqual(
            "what comes next, is a comma: ,\n",
            self.lyrics_to_str(lyrics)
        )

    def test_highlighted_notes(self):
        lyrics = self.parse("{1,normal} {!1,hl1} {!!1,hl2}")
        self.assertEqual("normal *hl1* _hl2_", self.lyrics_to_str(lyrics).strip())

    def test_ruby(self):
        lyrics = self.parse("{1,the_text|the_ruby}").dump()
        note = lyrics["stanzas"][0]["lines"][0]["notes"][0]
        self.assertEqual("the_text", note["text"])
        self.assertEqual("the_ruby", note["ruby"])

    def test_first_and_last_frames_are_calculated_from_durations(self):
        lyrics = self.parse(
"""
{FPS=100}
{BPM=60}

{1,four-sec} {2,eight-sec} {4/8,two-sec} {1/4,one-sec}
{1/8,half-sec} {1/64,2/64,1/64,quarter-sec} {0,zero-sec}
{1/32,eigth-sec}
"""
        )
        self.assertEqual(
"""\
[0,1588]
[0,1500] [0,400]four-sec [400,1200]eight-sec [1200,1400]two-sec [1400,1500]one-sec
[1500,1575] [1500,1550]half-sec [1550,1575]quarter-sec [1575,1575]zero-sec
[1575,1588] [1575,1588]eigth-sec
""",
            self.lyrics_to_str(lyrics, with_frames=True)
        )
        self.assertEqual([401], lyrics.stanzas[0].lines[0].notes[0].durations)
        self.assertEqual([6, 13, 7], lyrics.stanzas[0].lines[1].notes[1].durations)

    def test_calculating_reveal_positions_by_frame_number(self):
        lyrics = self.parse(
"""
{FPS=10}
{BPM=60}
{WIDTH=200}
{HEIGHT=50}
{TEXT_SIZE=10}
{RUBY_SIZE=1}
{BORDER_WIDTH=5}
{LINE_DISTANCE=16}
{RUBY_DISTANCE=1}
{DOT_SIZE=2}
{DOT=#000000}

{1,the first line is almost trivial; this note is 4 beats, ie. 40 frames}
{1/4,12345} {1/4,0/4,3/4,1/4,123456789}
"""
        )
        line = lyrics.stanzas[0].lines[1]

        self.assert_reveal_pos(((2, (0, 0, 0), (30, 30)), (25, 30, 0, 0)), line, 0)
        self.assert_reveal_pos(((2, (0, 0, 0), (30, 30)), (25, 30, 0, 0)), line, 39)
        self.assert_reveal_pos(((2, (0, 0, 0), (170, 30)), (25, 30, 150, 22)), line, 100)
        self.assert_reveal_pos(((2, (0, 0, 0), (170, 30)), (25, 30, 150, 22)), line, 999)

        self.assert_reveal_pos(((2, (0, 0, 0), (55, 23)), (25, 30, 30, 22)), line, 45)
        self.assert_reveal_pos(((2, (0, 0, 0), (80, 30)), (25, 30, 55, 22)), line, 50)

        self.assert_reveal_pos(((2, (0, 0, 0), (102, 30)), (25, 30, 77, 22)), line, 59)
        self.assert_reveal_pos(((2, (0, 0, 0), (125, 30)), (25, 30, 100, 22)), line, 60)
        self.assert_reveal_pos(((2, (0, 0, 0), (125, 28)), (25, 30, 100, 22)), line, 61)
        self.assert_reveal_pos(((2, (0, 0, 0), (126, 27)), (25, 30, 101, 22)), line, 62)

    def assert_reveal_pos(self, expected, line, frame):
        self.assertEqual(
            expected,
            line.get_reveal_pos(frame),
            msg="Unexpected reveal positions for frame {!r}".format(frame)
        )

    def test_min_values_are_accepted(self):
        self.assert_parsed(
"""\
{BACKGROUND=#000000}
{SHADOW=#000000}
{SHADOW_BORDER=#000000}
{BORDER=#000000}
{TEXT=#000000}
{RUBY=#000000}
{HL1=#000000}
{HL2=#000000}
{DOT=#000000}
{FONT=Font1}

{FPS=1}
{WIDTH=1}
{HEIGHT=1}
{LINE_DISTANCE=0}
{BPM=1}
{TEXT_SIZE=1}
{RUBY_SIZE=1}
{RUBY_DISTANCE=0}
{BORDER_WIDTH=0}
{DOT_SIZE=0}

{1,t|r}
""",
            {
                "background": (0, 0, 0),
                "fps": 1,
                "height": 1,
                "last_frame": 240,
                "width": 1,
                "stanzas": [
                    {
                        "first_frame": 0,
                        "height": 2,
                        "last_frame": 240,
                        "line_distance": 0,
                        "lines": [
                            {
                                "first_frame": 0,
                                "height": 2,
                                "last_frame": 240,
                                "left": 0,
                                "middle_y": 0,
                                "line_distance": 0,
                                "width": 1,
                                "notes": [
                                    {
                                        "durations": [241],
                                        "first_frame": 0,
                                        "height": 2,
                                        "highlight": "normal",
                                        "last_frame": 240,
                                        "ruby": "r",
                                        "ruby_color": (0, 0, 0),
                                        "ruby_left": 0,
                                        "ruby_top": -1,
                                        "ruby_width": 1,
                                        "text": "t",
                                        "text_color": (0, 0, 0),
                                        "text_left": 0,
                                        "text_top": 0,
                                        "text_width": 1,
                                        "top": -1,
                                        "width": 1,
                                        "style": {
                                            "border_color": (0, 0, 0),
                                            "border_width": 0,
                                            "bpm": 1,
                                            "font": "Font1",
                                            "hl1_color": (0, 0, 0),
                                            "hl2_color": (0, 0, 0),
                                            "ruby_color": (0, 0, 0),
                                            "ruby_distance": 0,
                                            "ruby_size": 1,
                                            "shadow_border_color": (0, 0, 0),
                                            "shadow_color": (0, 0, 0),
                                            "text_color": (0, 0, 0),
                                            "text_size": 1,
                                            "dot_size": 0,
                                            "dot_color": (0, 0, 0),
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                ],
            }
        )

    def test_positions_and_styles_are_calculated_incrementally(self):
        lyrics = """\
{WIDTH=2000}
{HEIGHT=720}
{LINE_DISTANCE=35}
{FPS=100}

{BPM=60}\\
{FONT=Font1}\\
{TEXT_SIZE=100}\\
{RUBY_SIZE=10}\\
{RUBY_DISTANCE=1}\\
{BORDER_WIDTH=1}\\
{SHADOW=#118080}\\
{SHADOW_BORDER=#114040}\\
{BORDER=#11e0e0}\\
{TEXT=#11ffff}\\
{RUBY=#11e0e0}\\
{HL1=#1180ff}\\
{HL2=#11ff80}\\
{DOT=#11ffff}\\
{DOT_SIZE=11}\\
{1/4,note1|ruby1}\\
{BPM=120}\\
{FONT=Font2}\\
{TEXT_SIZE=200}\\
{RUBY_SIZE=20}\\
{RUBY_DISTANCE=2}\\
{BORDER_WIDTH=2}\\
{SHADOW=#228080}\\
{SHADOW_BORDER=#224040}\\
{BORDER=#22e0e0}\\
{TEXT=#22ffff}\\
{RUBY=#22e0e0}\\
{HL1=#2280ff}\\
{HL2=#22ff80}\\
{DOT=#22ffff}\\
{DOT_SIZE=22}\\
{1/4,note2}
{TEXT_SIZE=300}\\
{RUBY_SIZE=30}\\
{RUBY_DISTANCE=3}\\
{1/4,note3|ruby3}
"""
        self.assert_parsed(
            lyrics,
            {
                "background": Style.GREEN,
                "fps": 100,
                "height": 720,
                "width": 2000,
                "last_frame": 200,
                "stanzas": [
                    {
                        "height": 590,
                        "line_distance": 35,
                        "first_frame": 0,
                        "last_frame": 200,
                        "lines": [
                            {
                                "left": 250,
                                "middle_y": 176,
                                "width": 1500,
                                "height": 222,
                                "first_frame": 0,
                                "last_frame": 150,
                                "line_distance": 35,
                                "notes": [
                                    {
                                        "height": 111,
                                        "highlight": "normal",
                                        "ruby": "ruby1",
                                        "ruby_color": (17, 224, 224),
                                        "ruby_width": 50,
                                        "text": "note1",
                                        "text_color": (17, 255, 255),
                                        "text_width": 500,
                                        "width": 500,
                                        "first_frame": 0,
                                        "last_frame": 100,
                                        "durations": [101],
                                        "text_top": 131,
                                        "text_left": 250,
                                        "ruby_top": 120,
                                        "ruby_left": 475,
                                        "top": 120,
                                        "style": {
                                            "border_color": (17, 224, 224),
                                            "border_width": 1,
                                            "bpm": 60,
                                            "font": "Font1",
                                            "hl1_color": (17, 128, 255),
                                            "hl2_color": (17, 255, 128),
                                            "ruby_color": (17, 224, 224),
                                            "ruby_distance": 1,
                                            "ruby_size": 10,
                                            "shadow_border_color": (17, 64, 64),
                                            "shadow_color": (17, 128, 128),
                                            "text_color": (17, 255, 255),
                                            "text_size": 100,
                                            "dot_color": (17, 255, 255),
                                            "dot_size": 11,
                                        },
                                    },
                                    {
                                        "height": 222,
                                        "highlight": "normal",
                                        "ruby": "",
                                        "ruby_color": (34, 224, 224),
                                        "ruby_width": 0,
                                        "text": "note2",
                                        "text_color": (34, 255, 255),
                                        "text_width": 1000,
                                        "width": 1000,
                                        "first_frame": 100,
                                        "last_frame": 150,
                                        "durations": [51],
                                        "text_top": 87,
                                        "text_left": 750,
                                        "ruby_top": 65,
                                        "ruby_left": 1250,
                                        "top": 87,
                                        "style": {
                                            "border_color": (34, 224, 224),
                                            "border_width": 2,
                                            "bpm": 120,
                                            "font": "Font2",
                                            "hl1_color": (34, 128, 255),
                                            "hl2_color": (34, 255, 128),
                                            "ruby_color": (34, 224, 224),
                                            "ruby_distance": 2,
                                            "ruby_size": 20,
                                            "shadow_border_color": (34, 64, 64),
                                            "shadow_color": (34, 128, 128),
                                            "text_color": (34, 255, 255),
                                            "text_size": 200,
                                            "dot_color": (34, 255, 255),
                                            "dot_size": 22,
                                        },
                                    },
                                ],
                            },
                            {
                                "left": 250,
                                "middle_y": 433,
                                "width": 1500,
                                "height": 333,
                                "first_frame": 150,
                                "last_frame": 200,
                                "line_distance": 35,
                                "notes": [
                                    {
                                        "height": 333,
                                        "highlight": "normal",
                                        "ruby": "ruby3",
                                        "ruby_color": (34, 224, 224),
                                        "ruby_width": 150,
                                        "text": "note3",
                                        "text_color": (34, 255, 255),
                                        "text_width": 1500,
                                        "width": 1500,
                                        "first_frame": 150,
                                        "last_frame": 200,
                                        "durations": [51],
                                        "text_top": 299,
                                        "text_left": 250,
                                        "ruby_top": 266,
                                        "ruby_left": 925,
                                        "top": 266,
                                        "style": {
                                            "border_color": (34, 224, 224),
                                            "border_width": 2,
                                            "bpm": 120,
                                            "font": "Font2",
                                            "hl1_color": (34, 128, 255),
                                            "hl2_color": (34, 255, 128),
                                            "ruby_color": (34, 224, 224),
                                            "ruby_distance": 3,
                                            "ruby_size": 30,
                                            "shadow_border_color": (34, 64, 64),
                                            "shadow_color": (34, 128, 128),
                                            "text_color": (34, 255, 255),
                                            "text_size": 300,
                                            "dot_color": (34, 255, 255),
                                            "dot_size": 22,
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                ],
            }
        )

    def assert_parsed(self, text, expected):
        self.assertEqual(expected, self.parse(text).dump())

    def parse(self, text):
        p = Parser(FakeImageDraw(), FakeFonts)

        return p.parse(text)

    def lyrics_to_str(self, lyrics, *, with_frames=False):
        def frames(obj, suffix):
            if with_frames:
                return "[{},{}]{}".format(obj["first_frame"], obj["last_frame"], suffix)

            return ""

        def note_to_str(note):
            text = note["text"]

            if note["highlight"] == Note.HL1:
                text = "*{}*".format(text)
            elif note["highlight"] == Note.HL2:
                text = "_{}_".format(text)

            return frames(note, "") + text

        def line_to_str(line):
            return frames(line, " ") + " ".join([note_to_str(n) for n in line["notes"]])

        def stanza_to_str(stanza):
            return frames(stanza, "\n") + "\n".join([line_to_str(l) for l in stanza["lines"]])

        dump = lyrics.dump()

        return "\n\n".join([stanza_to_str(s) for s in dump["stanzas"]]) + "\n"


class FakeFonts:
    @classmethod
    def get(cls, name, size):
        return FakeFont(name, size)


class FakeFont:
    def __init__(self, name, size):
        self.name = name
        self.size = size


class FakeImageDraw:
    def textsize(self, text, font):
        return (font.size * len(text), font.size)


def run_tests():
    import json
    import sys

    test = TestParser()
    passed = 0
    failed = 0
    failures = []

    for attr_name in dir(test):
        if not attr_name.startswith("test_"):
            continue

        attr = getattr(test, attr_name, None)

        if not callable(attr):
            continue

        try:
            attr()
            passed += 1
        except Exception as exc:
            failed += 1
            failures.append(f"{attr_name=}, {type(exc)=}\n\n{exc}\n\n---\n\n")

    results = {
        "passed": passed,
        "failed": failed,
        "perf": 0.0,
        "failures": failures,
    }

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run_tests()


