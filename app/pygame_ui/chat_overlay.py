"""Chat overlay for the RAG Referee in PyGame UI."""

import queue
import pygame


class ChatOverlay:
    """Toggleable chat overlay for asking the RAG Referee questions."""

    # Colors
    BACKDROP_ALPHA = 180
    BG_COLOR = (33, 37, 43)
    BORDER_COLOR = (80, 80, 90)
    TITLE_COLOR = (220, 220, 220)
    INPUT_BG = (25, 28, 34)
    INPUT_BORDER = (60, 65, 75)
    INPUT_TEXT_COLOR = (220, 220, 220)
    PLACEHOLDER_COLOR = (100, 100, 110)
    USER_COLOR = (200, 210, 220)
    REFEREE_COLOR = (255, 215, 0)
    SYSTEM_COLOR = (150, 150, 160)
    THINKING_COLOR = (180, 180, 100)
    CLOSE_COLOR = (180, 60, 60)
    CLOSE_HOVER_COLOR = (220, 80, 80)
    SEPARATOR_COLOR = (60, 65, 75)

    def __init__(self, screen_width, screen_height):
        self.width = 520
        self.height = 520
        self.x = (screen_width - self.width) // 2
        self.y = (screen_height - self.height) // 2

        self.visible = False
        self.messages = []  # [{"role": "user"|"referee"|"system", "text": str}]
        self.input_text = ""
        self.is_thinking = False
        self.scroll_offset = 0
        self.pending_question = None
        self.referee_ready = False
        self.referee_error = None

        # Thread-safe queue for async answers
        self._answer_queue = queue.Queue()

        # Layout constants
        self.title_height = 40
        self.input_height = 44
        self.padding = 12
        self.msg_area_top = self.y + self.title_height
        self.msg_area_bottom = self.y + self.height - self.input_height
        self.msg_area_height = self.msg_area_bottom - self.msg_area_top

        # Close button rect (top-right)
        self.close_rect = pygame.Rect(
            self.x + self.width - 36, self.y + 6, 28, 28
        )
        self._close_hover = False

        # Fonts (initialized lazily)
        self._fonts_initialized = False
        self._title_font = None
        self._msg_font = None
        self._input_font = None
        self._label_font = None

        # Cached message surfaces (invalidated when messages change)
        self._cached_lines = None
        self._cached_msg_count = -1
        self._thinking_dots = 0
        self._thinking_timer = 0

    def _init_fonts(self):
        if self._fonts_initialized:
            return
        self._title_font = pygame.font.Font(None, 28)
        self._msg_font = pygame.font.Font(None, 22)
        self._input_font = pygame.font.Font(None, 24)
        self._label_font = pygame.font.Font(None, 18)
        self._fonts_initialized = True

    def show(self):
        self.visible = True
        self.scroll_offset = 0

    def hide(self):
        self.visible = False
        self.pending_question = None

    def receive_answer(self, answer_text):
        """Called from background thread by AIInterface callback."""
        self._answer_queue.put(answer_text)

    def update(self):
        """Called each frame. Drains answer queue and updates animations."""
        if not self.visible:
            return

        # Drain answer queue
        try:
            while True:
                answer = self._answer_queue.get_nowait()
                self.messages.append({"role": "referee", "text": answer})
                self.is_thinking = False
                self.scroll_offset = 0
                self._cached_msg_count = -1  # invalidate cache
        except queue.Empty:
            pass

        # Animate thinking dots
        if self.is_thinking:
            self._thinking_timer += 1
            if self._thinking_timer % 30 == 0:
                self._thinking_dots = (self._thinking_dots + 1) % 4

    def handle_event(self, event):
        """Handle an event. Returns True if consumed."""
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.close_rect.collidepoint(event.pos):
                    self.hide()
                    return True
                # Consume click if inside overlay
                overlay_rect = pygame.Rect(self.x, self.y, self.width, self.height)
                if overlay_rect.collidepoint(event.pos):
                    return True
            return True  # consume all clicks when visible

        if event.type == pygame.MOUSEMOTION:
            self._close_hover = self.close_rect.collidepoint(event.pos)
            return True

        if event.type == pygame.MOUSEWHEEL:
            self.scroll_offset = max(0, self.scroll_offset - event.y * 20)
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True

            if event.key == pygame.K_RETURN:
                text = self.input_text.strip()
                if text and not self.is_thinking:
                    self.messages.append({"role": "user", "text": text})
                    
                    self.pending_question = text
                    self.input_text = ""
                    self.is_thinking = True
                    self.scroll_offset = 0
                    self._thinking_dots = 0
                    self._thinking_timer = 0
                    self._cached_msg_count = -1
                return True

            if event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                return True

            if event.unicode and event.unicode.isprintable():
                self.input_text += event.unicode
                return True

            return True

        return True  # consume all events when visible

    def _wrap_text(self, text, font, max_width):
        """Word-wrap text to fit within max_width pixels, preserving newlines."""
        lines = []
        # Split into paragraphs to preserve newlines from LLM
        paragraphs = text.splitlines()
        if not paragraphs:
            return [""]

        for paragraph in paragraphs:
            # Preserve empty lines (paragraph breaks)
            if not paragraph:
                lines.append("")
                continue

            words = paragraph.split()
            if not words:
                lines.append("")
                continue

            # Simple heuristic for bullet points to indent wrapped lines
            indent = ""
            if words[0] in ["-", "*", "•"] or (len(words[0]) > 1 and words[0].endswith(".") and words[0][:-1].isdigit()):
                indent = "    "

            current = words[0]
            for word in words[1:]:
                test = current + " " + word
                if font.size(test)[0] <= max_width:
                    current = test
                else:
                    lines.append(current)
                    current = indent + word
            lines.append(current)
            
        return lines

    def _build_lines(self):
        """Build rendered lines from messages. Returns list of (surface, role)."""
        self._init_fonts()
        max_text_width = self.width - self.padding * 4
        lines = []

        for msg in self.messages:
            role = msg["role"]
            if role == "user":
                color = self.USER_COLOR
                prefix = "You: "
            elif role == "referee":
                color = self.REFEREE_COLOR
                prefix = "Referee: "
            else:
                color = self.SYSTEM_COLOR
                prefix = ""

            # Clean up markdown bolding for cleaner display
            full_text = prefix + msg["text"].replace("**", "")
            wrapped = self._wrap_text(full_text, self._msg_font, max_text_width)
            for line_text in wrapped:
                surf = self._msg_font.render(line_text, True, color)
                lines.append((surf, role))

            # Blank line between messages
            lines.append((None, "spacer"))

        return lines

    def draw(self, surface):
        """Draw the chat overlay."""
        if not self.visible:
            return

        self._init_fonts()

        # Semi-transparent backdrop
        backdrop = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, self.BACKDROP_ALPHA))
        surface.blit(backdrop, (0, 0))

        # Main panel
        panel_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        pygame.draw.rect(surface, self.BG_COLOR, panel_rect, border_radius=8)
        pygame.draw.rect(surface, self.BORDER_COLOR, panel_rect, 2, border_radius=8)

        # Title bar
        title_text = "Ask the Referee"
        if not self.referee_ready:
            if self.referee_error:
                title_text += "  (unavailable)"
            else:
                title_text += "  (loading...)"
        title_surf = self._title_font.render(title_text, True, self.TITLE_COLOR)
        surface.blit(title_surf, (self.x + self.padding, self.y + 10))

        # Close button
        close_color = self.CLOSE_HOVER_COLOR if self._close_hover else self.CLOSE_COLOR
        pygame.draw.rect(surface, close_color, self.close_rect, border_radius=4)
        x_surf = self._title_font.render("X", True, (255, 255, 255))
        x_rect = x_surf.get_rect(center=self.close_rect.center)
        surface.blit(x_surf, x_rect)

        # Separator below title
        sep_y = self.y + self.title_height
        pygame.draw.line(
            surface, self.SEPARATOR_COLOR,
            (self.x + 1, sep_y), (self.x + self.width - 1, sep_y)
        )

        # Message area (clipped)
        msg_clip = pygame.Rect(
            self.x + self.padding,
            self.msg_area_top + 4,
            self.width - self.padding * 2,
            self.msg_area_height - 8,
        )
        old_clip = surface.get_clip()
        surface.set_clip(msg_clip)

        # Build lines
        lines = self._build_lines()

        # Add "Thinking..." if waiting
        if self.is_thinking:
            dots = "." * (self._thinking_dots + 1)
            thinking_surf = self._msg_font.render(
                f"Referee is thinking{dots}", True, self.THINKING_COLOR
            )
            lines.append((thinking_surf, "system"))

        # Calculate total content height
        line_height = 20
        spacer_height = 8
        total_height = 0
        for surf, role in lines:
            total_height += spacer_height if surf is None else line_height

        # Clamp scroll
        visible_height = msg_clip.height
        max_scroll = max(0, total_height - visible_height)
        self.scroll_offset = min(self.scroll_offset, max_scroll)

        # Draw messages from bottom (most recent visible by default)
        y_cursor = self.msg_area_top + 4 - self.scroll_offset + max(0, visible_height - total_height)
        for surf, role in lines:
            if surf is None:
                y_cursor += spacer_height
                continue
            if self.msg_area_top <= y_cursor < self.msg_area_bottom:
                surface.blit(surf, (self.x + self.padding * 2, y_cursor))
            y_cursor += line_height

        surface.set_clip(old_clip)

        # Separator above input
        input_sep_y = self.msg_area_bottom
        pygame.draw.line(
            surface, self.SEPARATOR_COLOR,
            (self.x + 1, input_sep_y), (self.x + self.width - 1, input_sep_y)
        )

        # Input area
        input_rect = pygame.Rect(
            self.x + self.padding,
            self.msg_area_bottom + 6,
            self.width - self.padding * 2,
            self.input_height - 12,
        )
        pygame.draw.rect(surface, self.INPUT_BG, input_rect, border_radius=4)
        pygame.draw.rect(surface, self.INPUT_BORDER, input_rect, 1, border_radius=4)

        if self.input_text:
            # Render input text (truncate from left if too wide)
            display_text = self.input_text + "_"
            text_surf = self._input_font.render(display_text, True, self.INPUT_TEXT_COLOR)
            max_input_w = input_rect.width - 12
            if text_surf.get_width() > max_input_w:
                # Show the rightmost portion
                crop_rect = pygame.Rect(
                    text_surf.get_width() - max_input_w, 0,
                    max_input_w, text_surf.get_height()
                )
                text_surf = text_surf.subsurface(crop_rect)
            surface.blit(text_surf, (input_rect.x + 6, input_rect.y + 5))
        elif not self.is_thinking:
            placeholder = self._input_font.render(
                "Ask a question...", True, self.PLACEHOLDER_COLOR
            )
            surface.blit(placeholder, (input_rect.x + 6, input_rect.y + 5))
        else:
            waiting = self._input_font.render(
                "Waiting for answer...", True, self.PLACEHOLDER_COLOR
            )
            surface.blit(waiting, (input_rect.x + 6, input_rect.y + 5))
