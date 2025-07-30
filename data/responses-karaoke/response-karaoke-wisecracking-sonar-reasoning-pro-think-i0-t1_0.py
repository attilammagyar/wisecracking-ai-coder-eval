# --- BEGIN GENERATED CODE ---
import re
import math
from fractions import Fraction
from PIL import ImageDraw, ImageFont

DEFAULT_FONT = "/usr/share/fonts/truetype/takao-mincho/TakaoMincho.ttf"

class Fonts:
    CACHE = {}

    @classmethod
    def get(cls, name, size):
        key = f"{name},{size}"
        if key not in cls.CACHE:
            cls.CACHE[key] = ImageFont.truetype(name, size)
        return cls.CACHE[key]

class Parser:
    GLOBAL_SETTINGS = {
        "BACKGROUND", "FPS", "HEIGHT", "LINE_DISTANCE", "WIDTH"
    }
    
    COMMAND_RE = re.compile(r"\{([^}]*)\}")
    SETTING_RE = re.compile(r"^([A-Z0-9_]+)=(.*)$")
    COLOR_RE = re.compile(r"^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$")
    NOTE_RE = re.compile(r"^(!{0,2})(([0-9]+(/[1-9][0-9]*)?,)+)([^|]*)(\|(.*))?$")

    def __init__(self, image_draw, fonts=Fonts):
        self.image_draw = image_draw
        self.fonts = fonts
        self.reset()

    def reset(self):
        self.stanzas = []
        self.lines = []
        self.notes = []
        self.width = 1280
        self.height = 720
        self.line_distance = 35
        self.fps = 30
        self.background = Style.GREEN
        self.style = Style()
        self.time = 0
        self.line_number = 0
        self.has_notes = False

    def parse(self, text):
        self.reset()
        
        for stanza in text.split("\n\n"):
            stanza = stanza.strip()
            if not stanza:
                continue
                
            self.lines = []
            self.notes = []
            
            for line in stanza.split("\n"):
                self.line_number += 1
                line = line.strip()
                
                for command in self.COMMAND_RE.findall(line):
                    if setting_match := self.SETTING_RE.match(command):
                        self.parse_setting(setting_match)
                    elif note_match := self.NOTE_RE.match(command):
                        self.parse_note(note_match)
                    else:
                        raise InvalidCommand(command, "invalid command", self.line_number)
                
                if not line.endswith("\\") and self.notes:
                    self.lines.append(Line(self.notes, self.width, 0, self.line_distance))
                    self.notes = []
            
            if self.notes:
                self.lines.append(Line(self.notes, self.width, 0, self.line_distance))
                self.notes = []
                
            if self.lines:
                self.stanzas.append(Stanza(self.lines, self.height, self.line_distance))
        
        return Lyrics(
            self.stanzas,
            self.width,
            self.height,
            self.fps,
            self.background
        )

    def parse_setting(self, match):
        name, value = match.group(1), match.group(2)
        
        if name in self.GLOBAL_SETTINGS and self.has_notes:
            raise GlobalSettingsMustBeSpecifiedBeforeFirstNote(
                match.group(0), "global settings must be specified before first note", self.line_number
            )
            
        if name == "FPS":
            self.fps = self.parse_positive_int(value)
        elif name == "BACKGROUND":
            self.background = self.parse_html_color(value)
        elif name == "WIDTH":
            self.width = self.parse_positive_int(value)
        elif name == "HEIGHT":
            self.height = self.parse_positive_int(value)
        elif name == "LINE_DISTANCE":
            self.line_distance = self.parse_non_negative_int(value)
        elif name == "FONT":
            self.style = self.style.set_font(value)
        elif name == "BPM":
            self.style = self.style.set_bpm(self.parse_positive_int(value))
        elif name == "TEXT_SIZE":
            self.style = self.style.set_text_size(self.parse_positive_int(value))
        elif name == "RUBY_SIZE":
            self.style = self.style.set_ruby_size(self.parse_positive_int(value))
        elif name == "RUBY_DISTANCE":
            self.style = self.style.set_ruby_distance(self.parse_non_negative_int(value))
        elif name == "BORDER_WIDTH":
            self.style = self.style.set_border_width(self.parse_non_negative_int(value))
        elif name == "SHADOW":
            self.style = self.style.set_shadow_color(self.parse_html_color(value))
        elif name == "SHADOW_BORDER":
            self.style = self.style.set_shadow_border_color(self.parse_html_color(value))
        elif name == "BORDER":
            self.style = self.style.set_border_color(self.parse_html_color(value))
        elif name == "TEXT":
            self.style = self.style.set_text_color(self.parse_html_color(value))
        elif name == "RUBY":
            self.style = self.style.set_ruby_color(self.parse_html_color(value))
        elif name == "HL1":
            self.style = self.style.set_hl1_color(self.parse_html_color(value))
        elif name == "HL2":
            self.style = self.style.set_hl2_color(self.parse_html_color(value))
        elif name == "DOT":
            self.style = self.style.set_dot_color(self.parse_html_color(value))
        elif name == "DOT_SIZE":
            self.style = self.style.set_dot_size(self.parse_non_negative_int(value))
        else:
            raise UnknownSetting(match.group(0), "unknown setting", self.line_number)

    def parse_note(self, match):
        highlight = match.group(1)
        raw_durations = match.group(2).rstrip(',')
        text = match.group(5).strip()
        ruby = (match.group(7) or "").strip()
        
        duration_seconds = self.parse_durations(raw_durations)
        first_frame = self.seconds_to_frames(self.time)
        self.time += sum(duration_seconds)
        last_frame = self.seconds_to_frames(self.time)
        
        total_frames = last_frame - first_frame + 1
        frame_durations = [self.seconds_to_frames(d) for d in duration_seconds]
        frame_durations[-1] = total_frames - sum(frame_durations[:-1])
        
        if highlight == "!":
            highlight = Note.HL1
        elif highlight == "!!":
            highlight = Note.HL2
        else:
            highlight = Note.NORMAL
            
        self.has_notes = True
        
        self.notes.append(
            Note(
                self.image_draw,
                text,
                ruby,
                self.style,
                highlight,
                frame_durations,
                first_frame,
                last_frame,
                self.fonts
            )
        )
    
    def seconds_to_frames(self, seconds):
        return int(seconds * self.fps + 0.5)
    
    def parse_durations(self, raw_durations):
        durations = []
        for d in raw_durations.split(','):
            if not d:
                continue
            if '/' in d:
                num, denom = d.split('/')
                fraction = Fraction(int(num), int(denom))
            else:
                fraction = Fraction(int(d))
            seconds = (fraction * 240) / self.style.bpm
            durations.append(float(seconds))
        return durations
    
    def parse_html_color(self, color):
        if m := self.COLOR_RE.match(color):
            return tuple(int(n, 16) for n in m.groups())
        raise InvalidColor(color, "expected #RRGGBB format", self.line_number)
    
    def parse_positive_int(self, n):
        return self.parse_int(n, min_value=1, error_msg="positive, non-zero")
    
    def parse_non_negative_int(self, n):
        return self.parse_int(n, min_value=0, error_msg="non-negative")
    
    def parse_int(self, n, min_value, error_msg):
        try:
            value = int(n)
            if value < min_value:
                raise ValueError()
            return value
        except Exception as e:
            raise InvalidInteger(n, f"expected {error_msg} integer", self.line_number, e) from e

class Lyrics:
    def __init__(self, stanzas, width, height, fps, background):
        self.stanzas = stanzas
        self.width = width
        self.height = height
        self.fps = fps
        self.background = background
        self.last_frame = max(s.last_frame for s in stanzas) if stanzas else 0
    
    def dump(self):
        return {
            "stanzas": [s.dump() for s in self.stanzas],
            "width": self.width,
            "height": self.height,
            "background": self.background,
            "fps": self.fps,
            "last_frame": self.last_frame,
        }

class Stanza:
    def __init__(self, lines, frame_height, line_distance):
        self.lines = lines
        self.line_distance = line_distance
        self.height = sum(line.height + line_distance for line in lines) - line_distance
        self.first_frame = min(line.first_frame for line in lines)
        self.last_frame = max(line.last_frame for line in lines)
        
        y_start = (frame_height - self.height) // 2
        current_y = y_start
        
        for line in lines:
            line.set_position(current_y)
            current_y += line.height + line_distance
    
    def dump(self):
        return {
            "height": self.height,
            "line_distance": self.line_distance,
            "lines": [line.dump() for line in self.lines],
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
        }

class Line:
    def __init__(self, notes, frame_width, middle_y, line_distance):
        self.notes = notes
        self.height = max(note.height for note in notes)
        self.width = sum(note.width for note in notes)
        self.left = (frame_width - self.width) // 2
        self.first_frame = notes[0].first_frame
        self.last_frame = notes[-1].last_frame
        self.line_distance = line_distance
        self.middle_y = None
        self.bbox_top = None
        self.bbox_left = None
        self.bbox_width = None
        self.bbox_height = None
    
    def set_position(self, y):
        self.middle_y = y
        self.top = y - self.height // 2
        
        cursor_x = self.left
        for note in self.notes:
            note.set_position(self.top, cursor_x)
            cursor_x += note.width
        
        self.bbox_top = min(note.top - note.style.border_width for note in self.notes)
        self.bbox_left = self.left - self.notes[0].style.border_width
        self.bbox_height = max(
            note.height + 2 * note.style.border_width 
            for note in self.notes
        )
        self.bbox_width = self.width + \
            self.notes[0].style.border_width + \
            self.notes[-1].style.border_width
    
    def get_reveal_pos(self, frame):
        if frame < self.first_frame:
            note = self.notes[0]
            return (
                (note.style.dot_size, note.style.dot_color, 
                 (self.left, self.top - note.style.dot_size)),
                (self.bbox_left, self.bbox_top, 0, 0)
            )
        
        if frame >= self.last_frame:
            note = self.notes[-1]
            return (
                (note.style.dot_size, note.style.dot_color,
                 (self.left + self.width, self.top - note.style.dot_size)),
                (self.bbox_left, self.bbox_top, self.bbox_width, self.bbox_height)
            )
        
        border_left = self.notes[0].style.border_width
        revealed_width = 0
        dot_bounce = 0.0
        
        for note in self.notes:
            if frame < note.first_frame:
                break
                
            if frame <= note.last_frame:
                note_revealed, bounce = note.get_reveal_pos(frame)
                revealed_width += note_revealed
                dot_bounce = bounce
                break
                
            revealed_width += note.width
        
        dot_pos = None
        if dot_bounce > 0:
            note = next(n for n in self.notes if n.first_frame <= frame <= n.last_frame)
            dot_y = self.top - note.style.dot_size - int(
                dot_bounce * (self.line_distance - note.style.dot_size)
            )
            dot_pos = (self.left + revealed_width, dot_y)
        
        return (
            (note.style.dot_size, note.style.dot_color, dot_pos),
            (
                self.bbox_left,
                self.bbox_top,
                border_left + revealed_width,
                self.bbox_height
            )
        )
    
    def dump(self):
        return {
            "middle_y": self.middle_y,
            "width": self.width,
            "height": self.height,
            "left": self.left,
            "notes": [note.dump() for note in self.notes],
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "line_distance": self.line_distance,
        }

class Note:
    NORMAL = "normal"
    HL1 = "hl1"
    HL2 = "hl2"
    
    def __init__(self, image_draw, text, ruby, style, highlight, 
                 durations, first_frame, last_frame, fonts=Fonts):
        self.text = text
        self.ruby = ruby
        self.style = style
        self.highlight = highlight
        self.durations = durations
        self.first_frame = first_frame
        self.last_frame = last_frame
        
        # Calculate dimensions
        self.text_font = fonts.get(style.font, style.text_size)
        self.ruby_font = fonts.get(style.font, style.ruby_size)
        
        self.text_width = image_draw.textlength(text, font=self.text_font)
        self.ruby_width = image_draw.textlength(ruby, font=self.ruby_font) if ruby else 0
        self.width = max(self.text_width, self.ruby_width)
        
        self.height = style.text_size + style.ruby_distance + style.ruby_size
        
        # Set colors based on highlight
        if highlight == Note.HL1:
            self.text_color = style.hl1_color
            self.ruby_color = style.hl1_color
        elif highlight == Note.HL2:
            self.text_color = style.hl2_color
            self.ruby_color = style.hl2_color
        else:
            self.text_color = style.text_color
            self.ruby_color = style.ruby_color
        
        # Position will be set later
        self.top = None
        self.text_top = None
        self.text_left = None
        self.ruby_top = None
        self.ruby_left = None
    
    def set_position(self, line_top, left):
        self.top = line_top
        self.ruby_top = line_top
        self.text_top = line_top + self.style.ruby_size + self.style.ruby_distance
        
        # Center ruby text over main text
        ruby_offset = (self.text_width - self.ruby_width) / 2
        self.ruby_left = left + max(0, ruby_offset)
        self.text_left = left + max(0, -ruby_offset)
    
    def get_reveal_pos(self, frame):
        rel_frame = frame - self.first_frame
        total_duration = sum(self.durations)
        consumed_frames = 0
        current_duration_index = 0
        
        for i, duration in enumerate(self.durations):
            if rel_frame < consumed_frames + duration:
                current_duration_index = i
                break
            consumed_frames += duration
        else:
            return self.width, 0.0
        
        duration_in_part = rel_frame - consumed_frames
        current_duration = self.durations[current_duration_index]
        fraction = min(1.0, duration_in_part / current_duration)
        
        part_width = self.width / len(self.durations)
        revealed = (current_duration_index + fraction) * part_width
        
        # Calculate dot bounce (parabolic curve)
        dot_bounce = 4 * fraction * (1 - fraction)
        
        return int(revealed), dot_bounce
    
    def dump(self):
        return {
            "text": self.text,
            "ruby": self.ruby,
            "highlight": self.highlight,
            "text_color": self.text_color,
            "ruby_color": self.ruby_color,
            "text_width": self.text_width,
            "ruby_width": self.ruby_width,
            "width": self.width,
            "height": self.height,
            "style": self.style.dump(),
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "durations": self.durations,
            "text_top": self.text_top,
            "text_left": self.text_left,
            "ruby_top": self.ruby_top,
            "ruby_left": self.ruby_left,
            "top": self.top,
        }

class Style:
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GREY = (160, 160, 160)
    LIGHT_GREY = (224, 224, 224)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 128)
    LIGHT_RED = (255, 164, 132)
    LIGHT_BLUE = (168, 212, 255)
    YELLOW = (255, 255, 0)

    def __init__(self):
        self.bpm = 120
        self.font = DEFAULT_FONT
        self.text_size = 32
        self.ruby_size = 15
        self.ruby_distance = 2
        self.border_width = 2
        self.shadow_color = self.GREY
        self.shadow_border_color = self.BLACK
        self.text_color = self.WHITE
        self.ruby_color = self.LIGHT_GREY
        self.border_color = self.BLUE
        self.hl1_color = self.LIGHT_RED
        self.hl2_color = self.LIGHT_BLUE
        self.dot_color = self.YELLOW
        self.dot_size = 8

    def dump(self):
        return {k: v for k, v in vars(self).items() if not k.startswith('_')}
    
    def copy(self):
        new_style = Style()
        new_style.__dict__.update(self.__dict__)
        return new_style
    
    # All setter methods follow this pattern:
    def set_bpm(self, bpm):
        new = self.copy()
        new.bpm = bpm
        return new
        
    def set_font(self, font):
        new = self.copy()
        new.font = font
        return new
        
    def set_text_size(self, size):
        new = self.copy()
        new.text_size = size
        return new
        
    def set_ruby_size(self, size):
        new = self.copy()
        new.ruby_size = size
        return new
        
    def set_ruby_distance(self, distance):
        new = self.copy()
        new.ruby_distance = distance
        return new
        
    def set_border_width(self, width):
        new = self.copy()
        new.border_width = width
        return new
        
    def set_shadow_color(self, color):
        new = self.copy()
        new.shadow_color = color
        return new
        
    def set_shadow_border_color(self, color):
        new = self.copy()
        new.shadow_border_color = color
        return new
        
    def set_text_color(self, color):
        new = self.copy()
        new.text_color = color
        return new
        
    def set_ruby_color(self, color):
        new = self.copy()
        new.ruby_color = color
        return new
        
    def set_border_color(self, color):
        new = self.copy()
        new.border_color = color
        return new
        
    def set_hl1_color(self, color):
        new = self.copy()
        new.hl1_color = color
        return new
        
    def set_hl2_color(self, color):
        new = self.copy()
        new.hl2_color = color
        return new
        
    def set_dot_color(self, color):
        new = self.copy()
        new.dot_color = color
        return new
        
    def set_dot_size(self, size):
        new = self.copy()
        new.dot_size = size
        return new

# Exception classes remain unchanged
class ParseError(ValueError): ...
class InvalidCommand(ParseError): ...
class UnknownSetting(ParseError): ...
class InvalidInteger(ParseError): ...
class InvalidColor(ParseError): ...
class GlobalSettingsMustBeSpecifiedBeforeFirstNote(ParseError): ...
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


