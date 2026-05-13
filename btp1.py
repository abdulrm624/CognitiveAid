import json
import math
import os
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import random

from PIL import Image, ImageDraw, ImageTk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

APP_TITLE = "Cognitive Aid"
DATA_FILE = os.path.join(os.path.expanduser("~"), "Downloads", "memory_game_player_data.json")
LAPSE_THRESHOLD_MS = 8000
GAME_DURATION_MS = 4 * 60 * 1000
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 1000
RESULTS_PASSWORD = "btp123"

GAME_CATEGORIES = {
    "numbers": "Grid",
    "objects": "Objects",
}

GAME_MODES = {
    "normal":         "Normal",
    "reverse":        "Mental Reversal",
    "rotate_90":      "Grid Rotation 90°",
    "rotate_180":     "Grid Rotation 180°",
    "reverse_rot90":  "Reversal + Rotation 90°",
    "reverse_rot180": "Reversal + Rotation 180°",
    "letter_assoc":   "Letter Association",
    "letter_reverse": "Letter Reversal",
    "mixed":          "Mixed (Changes Each Level)",
}

# Pool of modes the "mixed" mode cycles through
MIXED_MODE_POOL = ["normal", "reverse", "rotate_90", "rotate_180", "letter_assoc"]

# Letters used in letter-association modes
LETTER_POOL = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Progression constants
TRIALS_TO_ADVANCE = 5      # Consecutive correct trials to level up
TRIALS_TO_RECOVER = 4      # Consecutive correct trials at lower level to return
LEVELS_PER_GRID_TIER = 4   # Complete this many levels to expand the grid (2,3,4,5 = 4 levels)
GRID_TIERS = [3, 4, 5]     # Grid sizes: 3x3 → 4x4 → 5x5

# Shape config: each of the 9 objects gets a unique color and size
SHAPE_CONFIGS = {
    1: {"label": "Shape A", "color": (135, 206, 250), "size": 220},
    2: {"label": "Shape B", "color": (135, 206, 250), "size": 180},
    3: {"label": "Shape C", "color": (135, 206, 250), "size": 260},
    4: {"label": "Shape D", "color": (135, 206, 250), "size": 170},
    5: {"label": "Shape E", "color": (135, 206, 250), "size": 210},
    6: {"label": "Shape F", "color": (135, 206, 250), "size": 190},
    7: {"label": "Shape G", "color": (135, 206, 250), "size": 240},
    8: {"label": "Shape H", "color": (135, 206, 250), "size": 160},
    9: {"label": "Shape I", "color": (135, 206, 250), "size": 200},
}

SHAPE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shapes")


def generate_random_blob(size: int, color: tuple, seed: int) -> Image.Image:
    """Generate a random squiggly blob shape with transparent background."""
    rng = random.Random(seed)
    img_size = size + 20  # padding
    img = Image.new("RGBA", (img_size, img_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = img_size // 2, img_size // 2
    base_r = size // 2

    # Generate random radii at evenly spaced angles to form a blob
    num_points = rng.randint(12, 22)
    angles = [2 * math.pi * i / num_points for i in range(num_points)]
    radii = [base_r * rng.uniform(0.3, 1.0) for _ in range(num_points)]

    # Build smooth outline by interpolating between points
    smooth_points = []
    for i in range(len(angles)):
        for t_frac in range(4):
            t = t_frac / 4.0
            i_next = (i + 1) % len(angles)
            angle = angles[i] + t * (angles[i_next] - angles[i] + (2 * math.pi if angles[i_next] < angles[i] else 0))
            r = radii[i] + t * (radii[i_next] - radii[i])
            smooth_points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    # Draw filled blob
    draw.polygon(smooth_points, fill=(*color, 200))
    # Draw outline
    draw.polygon(smooth_points, outline=(*color[:3], 255), width=2)

    return img


def ensure_shape_images() -> None:
    """Generate all 9 shape PNGs if they don't already exist."""
    os.makedirs(SHAPE_DIR, exist_ok=True)
    for num, cfg in SHAPE_CONFIGS.items():
        path = os.path.join(SHAPE_DIR, f"shape_{num}.png")
        if not os.path.exists(path):
            img = generate_random_blob(cfg["size"], cfg["color"], seed=num * 137)
            img.save(path, "PNG")

LEVELS = [
    {"level": 1, "count": 1, "show_ms": 1000, "gap_ms": 500},
    {"level": 2, "count": 2, "show_ms": 920, "gap_ms": 430},
    {"level": 3, "count": 3, "show_ms": 850, "gap_ms": 380},
    {"level": 4, "count": 4, "show_ms": 780, "gap_ms": 330},
    {"level": 5, "count": 5, "show_ms": 710, "gap_ms": 290},
    {"level": 6, "count": 6, "show_ms": 650, "gap_ms": 250},
    {"level": 7, "count": 7, "show_ms": 590, "gap_ms": 220},
    {"level": 8, "count": 8, "show_ms": 530, "gap_ms": 200},
    {"level": 9, "count": 9, "show_ms": 470, "gap_ms": 180},
]


@dataclass
class LapseEntry:
    started_at: str
    duration_ms: int
    trigger: str


class MemoryGameApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(1050, 760)
        self.root.configure(bg="#eef6fb")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Title.TLabel", font=("Arial", 24, "bold"), background="#eef6fb", foreground="#243447")
        self.style.configure("Subtitle.TLabel", font=("Arial", 11), background="#eef6fb", foreground="#4b5d73")
        self.style.configure("Action.TButton", font=("Arial", 11, "bold"), padding=8)

        self.player_store: Dict[str, object] = self.load_store()
        self.active_player_key: Optional[str] = None
        self.active_player: Optional[Dict[str, object]] = None

        self.started = False
        self.phase = "idle"  # idle, show_sequence, rotate_pause, input, input_letter, result, finished
        self.level_index = 1  # Start from level 2
        self.sequence: List[int] = []
        self.selected: List[int] = []
        self.score = 0
        self.stars = 0
        self.lives = 3
        self.best_score = 0
        self.message_text = tk.StringVar(value="Enter player details, choose a category and game type, then click Start Game.")
        self.timer_text = tk.StringVar(value="")
        self.reduced_distraction = tk.BooleanVar(value=True)
        self.player_name_var = tk.StringVar()
        self.player_age_var = tk.StringVar()
        self.game_mode_var = tk.StringVar(value="normal")
        self.game_category_var = tk.StringVar(value="numbers")
        self.game_mode_display_var = tk.StringVar(value=GAME_MODES["normal"])
        self.category_display_var = tk.StringVar(value=GAME_CATEGORIES["numbers"])

        # Progression system
        self.consecutive_correct = 0
        self.recovery_mode = False
        self.recovery_target_level = 0  # Level player fell from

        # Grid expansion (Grid category only)
        self.grid_tier_index = 0
        self.grid_size = GRID_TIERS[0]  # 3 = 3x3
        self.levels_completed_in_tier = 0

        # Letter association
        self.letter_assignments: Dict[int, str] = {}  # {cell_number: letter}
        self.waiting_for_letter = False
        self.letter_step_index = 0  # Which step in the sequence we expect a letter for

        # Mixed mode
        self.current_active_mode = "normal"  # The actual sub-mode active in mixed mode

        self.current_session = self.empty_session_stats()
        self.round_input_start_ms: Optional[int] = None
        self.pending_persisted = False

        self.last_app_activity_ms = int(time.time() * 1000)
        self.current_idle_lapse_start_ms: Optional[int] = None
        self.global_lapse_watch_job: Optional[str] = None

        self.show_job: Optional[str] = None
        self.next_round_job: Optional[str] = None
        self.session_timer_job: Optional[str] = None
        self.session_start_ms: Optional[int] = None
        self.stop_after_round = False

        self.number_buttons: Dict[int, tk.Button] = {}
        self.button_positions: Dict[int, tuple[int, int]] = {}
        self.rotation_degrees = 0

        # Floating animation state (objects mode only)
        self.floating_active = False
        self.float_animation_job: Optional[str] = None
        self.float_positions: Dict[int, list] = {}  # {number: [x, y, dx, dy]}
        self.grid_frame_width = 1100
        self.grid_frame_height = 800

        # Shape images (loaded once)
        self.shape_photo_images: Dict[int, ImageTk.PhotoImage] = {}
        self.shape_highlight_images: Dict[int, ImageTk.PhotoImage] = {}
        self.shape_selected_images: Dict[int, ImageTk.PhotoImage] = {}

        self.level_value_var = tk.StringVar(value="1")
        self.score_value_var = tk.StringVar(value="0")
        self.best_value_var = tk.StringVar(value="0")
        self.progress_var = tk.IntVar(value=0)
        self.stars_var = tk.StringVar(value="0")
        self.lives_var = tk.StringVar(value="❤ ❤ ❤")
        self.current_player_var = tk.StringVar(value="No player selected")
        self.all_time_sessions_var = tk.StringVar(value="0")
        self.all_time_rounds_var = tk.StringVar(value="0")
        self.lifetime_accuracy_var = tk.StringVar(value="0%")
        self.all_time_best_score_var = tk.StringVar(value="0")
        self.avg_response_var = tk.StringVar(value="0.0s")
        self.lapse_count_var = tk.StringVar(value="0")
        self.lapse_total_var = tk.StringVar(value="0.0s")
        self.avg_lapse_var = tk.StringVar(value="0.0s")
        self.progress_index_var = tk.StringVar(value="N/A")
        self.post_game_summary_var = tk.StringVar(value="")
        self.current_mode_display_var = tk.StringVar(value=GAME_MODES["normal"])
        self.current_submode_var = tk.StringVar(value="")
        self.feedback_var = tk.StringVar(value="")

        self.build_ui()
        self.load_last_player()

        self.root.bind_all("<Any-KeyPress>", self.record_app_activity, add="+")
        self.root.bind_all("<Any-ButtonPress>", self.record_app_activity, add="+")
        self.root.bind_all("<Motion>", self.record_app_activity, add="+")
        self.start_global_lapse_watch()

    def build_ui(self) -> None:
        outer = tk.Frame(self.root, bg="#eef6fb")
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        left_container = tk.Frame(outer, bg="#eef6fb")
        right = tk.Frame(outer, bg="#eef6fb")
        left_container.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right.pack(side="right", fill="y")

        # Scrollable left side
        left_canvas = tk.Canvas(left_container, bg="#eef6fb", highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left = tk.Frame(left_canvas, bg="#eef6fb")

        left_scrollbar.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_window = left_canvas.create_window((0, 0), window=left, anchor="nw")

        def on_left_configure(event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))

        def on_canvas_configure(event):
            left_canvas.itemconfigure(left_window, width=event.width)

        left.bind("<Configure>", on_left_configure)
        left_canvas.bind("<Configure>", on_canvas_configure)

        title_frame = tk.Frame(left, bg="#eef6fb")
        title_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(title_frame, text=APP_TITLE, style="Title.TLabel").pack(anchor="center")
        ttk.Label(
            title_frame,
            text="Choose a working-memory category and game type. Each session runs for 4 minutes.",
            style="Subtitle.TLabel",
        ).pack(anchor="center", pady=(5, 0))

        player_card = tk.Frame(left, bg="#ffffff", bd=1, relief="solid")
        player_card.pack(fill="x", pady=(0, 12))
        tk.Label(
            player_card,
            text="Player Details",
            font=("Arial", 14, "bold"),
            bg="#ffffff",
            fg="#243447"
        ).pack(anchor="w", padx=14, pady=(12, 8))

        form_row = tk.Frame(player_card, bg="#ffffff")
        form_row.pack(fill="x", padx=14, pady=(0, 10))

        name_col = tk.Frame(form_row, bg="#ffffff")
        age_col = tk.Frame(form_row, bg="#ffffff")
        cat_col = tk.Frame(form_row, bg="#ffffff")
        mode_col = tk.Frame(form_row, bg="#ffffff")

        name_col.pack(side="left", fill="x", expand=True, padx=(0, 8))
        age_col.pack(side="left", fill="x", expand=True, padx=(0, 8))
        cat_col.pack(side="left", fill="x", expand=True, padx=(0, 8))
        mode_col.pack(side="left", fill="x", expand=True)

        tk.Label(name_col, text="Name", font=("Arial", 10, "bold"), bg="#ffffff", fg="#243447").pack(anchor="w")
        tk.Entry(name_col, textvariable=self.player_name_var, font=("Arial", 12), relief="solid", bd=1).pack(fill="x", ipady=6, pady=(4, 0))

        tk.Label(age_col, text="Age", font=("Arial", 10, "bold"), bg="#ffffff", fg="#243447").pack(anchor="w")
        age_entry = tk.Entry(age_col, textvariable=self.player_age_var, font=("Arial", 12), relief="solid", bd=1)
        age_entry.pack(fill="x", ipady=6, pady=(4, 0))
        age_entry.bind("<KeyRelease>", self.only_digits_in_age)

        tk.Label(cat_col, text="Category", font=("Arial", 10, "bold"), bg="#ffffff", fg="#243447").pack(anchor="w")
        cat_menu = ttk.OptionMenu(
            cat_col,
            self.category_display_var,
            GAME_CATEGORIES["numbers"],
            *GAME_CATEGORIES.values(),
            command=self.on_category_menu_change,
        )
        cat_menu.pack(fill="x", pady=(4, 0), ipady=2)

        tk.Label(mode_col, text="Game Type", font=("Arial", 10, "bold"), bg="#ffffff", fg="#243447").pack(anchor="w")
        self.mode_menu = ttk.OptionMenu(
            mode_col,
            self.game_mode_display_var,
            GAME_MODES["normal"],
            *GAME_MODES.values(),
            command=self.on_mode_menu_change,
        )
        self.mode_menu.pack(fill="x", pady=(4, 0), ipady=2)

        tk.Label(
            player_card,
            textvariable=self.current_player_var,
            font=("Arial", 10),
            bg="#f5f8fb",
            fg="#36485c",
            padx=10,
            pady=8
        ).pack(fill="x", padx=14, pady=(0, 8))

        tk.Label(
            player_card,
            textvariable=self.current_mode_display_var,
            font=("Arial", 10, "bold"),
            bg="#f5f8fb",
            fg="#243447",
            padx=10,
            pady=8
        ).pack(fill="x", padx=14, pady=(0, 10))

        action_top = tk.Frame(player_card, bg="#ffffff")
        action_top.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Button(action_top, text="Start Game", style="Action.TButton", command=self.handle_start_game).pack(side="left", padx=(0, 8))
        ttk.Button(action_top, text="Reset", style="Action.TButton", command=self.reset_game).pack(side="left", padx=(0, 8))
        ttk.Button(action_top, text="Results", style="Action.TButton", command=self.open_results_with_password).pack(side="left")

        self.game_status_card = tk.Frame(left, bg="#ffffff", bd=1, relief="solid")
        self.game_status_card.pack(fill="x", pady=(0, 12))
        tk.Label(self.game_status_card, text="Game Status", font=("Arial", 13, "bold"), bg="#ffffff", fg="#243447").pack(anchor="w", padx=12, pady=(12, 8))
        gs_inner = tk.Frame(self.game_status_card, bg="#ffffff")
        gs_inner.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(gs_inner, textvariable=self.current_submode_var, font=("Arial", 11, "bold"), bg="#ffffff", fg="#0056b3", justify="left").pack(anchor="w", pady=(0, 4))
        tk.Label(
            gs_inner,
            textvariable=self.post_game_summary_var,
            font=("Arial", 10),
            bg="#ffffff",
            fg="#36485c",
            justify="left",
            wraplength=740,
        ).pack(anchor="w")

        game_card = tk.Frame(left, bg="#ffffff", bd=1, relief="solid")
        game_card.pack(fill="x", pady=(0, 12))

        stats_row = tk.Frame(game_card, bg="#ffffff")
        stats_row.pack(fill="x", padx=16, pady=(14, 10))
        self.build_top_stat(stats_row, "Level", self.level_value_var).pack(side="left", fill="x", expand=True)
        self.build_top_stat(stats_row, "Score", self.score_value_var).pack(side="left", fill="x", expand=True)
        self.build_top_stat(stats_row, "Best", self.best_value_var).pack(side="left", fill="x", expand=True)

        progress_frame = tk.Frame(game_card, bg="#ffffff")
        progress_frame.pack(fill="x", padx=16)
        tk.Label(progress_frame, text="Level Progress", font=("Arial", 10), bg="#ffffff", fg="#4b5d73").pack(anchor="w")
        ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100).pack(fill="x", pady=(4, 10))

        self.grid_frame = tk.Canvas(game_card, bg="#ffffff", highlightthickness=0)
        self.grid_frame.pack(pady=10)
        self.grid_frame.bind("<Button-1>", self.on_canvas_click)

        for number in range(1, 10):
            button = tk.Button(
                self.grid_frame,
                text="",
                font=("Arial", 22, "bold"),
                width=5,
                height=2,
                bg="#ffffff",
                fg="#243447",
                activebackground="#dceffd",
                relief="raised",
                bd=2,
                command=lambda n=number: self.handle_cell_click(n),
            )
            self.number_buttons[number] = button

        self.apply_grid_layout()

        message_box = tk.Frame(game_card, bg="#f5f8fb", bd=1, relief="solid")
        message_box.pack(fill="x", padx=16, pady=12)
        tk.Label(
            message_box,
            textvariable=self.message_text,
            font=("Arial", 12, "bold"),
            bg="#f5f8fb",
            fg="#243447",
            wraplength=700,
            justify="center",
            pady=8,
        ).pack()
        tk.Label(
            message_box,
            textvariable=self.timer_text,
            font=("Arial", 10),
            bg="#f5f8fb",
            fg="#5c7288"
        ).pack(pady=(0, 8))

        self.build_side_panel(right)
        self.refresh_grid_appearance()
        self.refresh_stats_display()

        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_btn4(event):
            left_canvas.yview_scroll(-1, "units")

        def _on_mousewheel_btn5(event):
            left_canvas.yview_scroll(1, "units")

        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        left_canvas.bind_all("<Button-4>", _on_mousewheel_btn4)
        left_canvas.bind_all("<Button-5>", _on_mousewheel_btn5)

    def on_mode_menu_change(self, label: str) -> None:
        mode_lookup = {value: key for key, value in GAME_MODES.items()}
        self.game_mode_var.set(mode_lookup.get(label, "normal"))
        self.on_mode_change()

    def on_category_menu_change(self, label: str) -> None:
        category_lookup = {value: key for key, value in GAME_CATEGORIES.items()}
        self.game_category_var.set(category_lookup.get(label, "numbers"))
        self.on_category_change()

    def set_mode_selection(self, mode_key: str) -> None:
        self.game_mode_var.set(mode_key)
        self.game_mode_display_var.set(GAME_MODES.get(mode_key, mode_key.title()))
        self.on_mode_change()

    def on_mode_change(self, _value=None) -> None:
        mode_key = self.game_mode_var.get()
        cat_key = self.game_category_var.get()
        cat_label = GAME_CATEGORIES.get(cat_key, cat_key)
        self.game_mode_display_var.set(GAME_MODES.get(mode_key, mode_key.title()))
        self.category_display_var.set(cat_label)
        self.current_mode_display_var.set(
            f"Current: {cat_label} — {GAME_MODES.get(mode_key, mode_key)}"
        )

    def on_category_change(self, _value=None) -> None:
        cat = self.game_category_var.get()
        menu = self.mode_menu["menu"]
        menu.delete(0, "end")
        
        if cat == "objects":
            allowed_modes = {"normal": "Normal", "reverse": "Mental Reversal"}
            if self.game_mode_var.get() not in allowed_modes:
                self.game_mode_var.set("normal")
                self.game_mode_display_var.set(GAME_MODES["normal"])
        else:
            allowed_modes = GAME_MODES
            
        for key, label in allowed_modes.items():
            menu.add_command(label=label, command=lambda k=key: self.set_mode_selection(k))
            
        self.update_button_faces()
        self.on_mode_change()

    def _load_blank_image(self) -> None:
        if not hasattr(self, "blank_img"):
            self.blank_img = ImageTk.PhotoImage(Image.new("RGBA", (1, 1), (255, 255, 255, 0)))

    def update_button_faces(self) -> None:
        """Update button text/font based on current category (Grid vs Objects)."""
        cat = self.game_category_var.get()
        total_cells = self.grid_size ** 2
        for number in range(1, total_cells + 1):
            if number not in self.number_buttons:
                continue
            btn = self.number_buttons[number]
            if cat == "objects":
                self._load_shape_images_if_needed()
                if number in self.shape_photo_images:
                    btn.configure(text="", image=self.shape_photo_images[number], width=0, height=0, compound="none")
            else:
                # Grid category: blank cells.
                self._load_blank_image()
                btn.configure(text="", font=("Arial", 22, "bold"), image=self.blank_img, compound="center", width=120, height=120)

    def _load_shape_images_if_needed(self) -> None:
        """Load shape PNGs into PhotoImage objects (once)."""
        if self.shape_photo_images:
            return
        ensure_shape_images()
        self.shape_pil_images = {}
        for num in range(1, 10):
            path = os.path.join(SHAPE_DIR, f"shape_{num}.png")
            pil_img = Image.open(path).convert("RGBA")
            self.shape_pil_images[num] = pil_img

            # Normal image
            self.shape_photo_images[num] = ImageTk.PhotoImage(pil_img)

            # Highlighted (yellow tint) version
            highlight = pil_img.copy()
            pixels = highlight.load()
            w, h = highlight.size
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    if a > 30:
                        pixels[x, y] = (255, 230, 100, a)
            self.shape_highlight_images[num] = ImageTk.PhotoImage(highlight)

            # Selected (blue tint) version
            selected = pil_img.copy()
            pixels = selected.load()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    if a > 30:
                        pixels[x, y] = (255, 180, 80, a)
            self.shape_selected_images[num] = ImageTk.PhotoImage(selected)

    def apply_grid_layout(self) -> None:
        self.stop_float_animation()
        for widget in self.grid_frame.winfo_children():
            widget.grid_forget()
            widget.place_forget()

        positions = self.get_rotated_positions(self.rotation_degrees)
        self.button_positions = {}
        total_cells = self.grid_size ** 2

        for number in range(1, total_cells + 1):
            if number not in self.number_buttons:
                continue
            row, col = positions[number]
            self.button_positions[number] = (row, col)
            self.number_buttons[number].grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        for i in range(self.grid_size):
            self.grid_frame.grid_columnconfigure(i, weight=1)
            self.grid_frame.grid_rowconfigure(i, weight=1)

    # ── Floating animation for objects mode ──────────────────────────

    def start_float_animation(self) -> None:
        """Remove buttons from grid and float transparent images on canvas."""
        self.stop_float_animation()

        self.grid_frame_width = 1200
        self.grid_frame_height = 900
        self.grid_frame.configure(width=self.grid_frame_width, height=self.grid_frame_height)
        self.grid_frame.pack_propagate(False)
        self.grid_frame.grid_propagate(False)

        for number in range(1, 10):
            self.number_buttons[number].grid_forget()
            self.number_buttons[number].place_forget()

        self._load_shape_images_if_needed()
        self.float_canvas_items = {}

        n = LEVELS[self.level_index]["level"]
        num_moving = 9 if n >= 4 else 2 * n
        moving_subset = set(range(1, num_moving + 1))

        row_h = self.grid_frame_height // 3
        col_w = self.grid_frame_width // 3

        self.float_positions = {}
        for number in range(1, 10):
            r = (number - 1) // 3
            c = (number - 1) % 3
            cfg = SHAPE_CONFIGS[number]
            size = cfg["size"]
            x = c * col_w + (col_w - size) // 2
            y = r * row_h + (row_h - size) // 2
            
            if number in moving_subset:
                dx = random.choice([-1.5, 1.5])
                dy = random.choice([-1.5, 1.5])
                self.float_positions[number] = [x, y, dx, dy]
            else:
                self.float_positions[number] = [x, y, 0, 0]
            
            item_id = self.grid_frame.create_image(
                x, y, 
                image=self.shape_photo_images[number], 
                anchor="nw",
                tags="float_shape"
            )
            self.float_canvas_items[number] = item_id

        self.floating_active = True
        self.float_animation_tick()

    def stop_float_animation(self) -> None:
        """Stop the floating animation and cancel the scheduled job."""
        self.floating_active = False
        if self.float_animation_job is not None:
            try:
                self.root.after_cancel(self.float_animation_job)
            except tk.TclError:
                pass
            self.float_animation_job = None
            
        # Clean up canvas images
        if hasattr(self, "grid_frame") and isinstance(self.grid_frame, tk.Canvas):
            self.grid_frame.delete("float_shape")
            if hasattr(self, "float_canvas_items"):
                self.float_canvas_items.clear()

    def float_animation_tick(self) -> None:
        """Move each shape a small step, bounce off edges and each other."""
        if not self.floating_active:
            return

        max_x = self.grid_frame_width
        max_y = self.grid_frame_height

        for number, pos in self.float_positions.items():
            if pos[2] == 0 and pos[3] == 0:
                continue
            x, y, dx, dy = pos
            size = SHAPE_CONFIGS[number]["size"]
            x += dx
            y += dy

            if x <= 0 or x + size >= max_x:
                dx = -dx
                x = max(0, min(x, max_x - size))
            if y <= 0 or y + size >= max_y:
                dy = -dy
                y = max(0, min(y, max_y - size))

            pos[0], pos[1], pos[2], pos[3] = x, y, dx, dy
            
        numbers = list(self.float_positions.keys())
        for i in range(len(numbers)):
            for j in range(i + 1, len(numbers)):
                n1 = numbers[i]
                n2 = numbers[j]
                p1 = self.float_positions[n1]
                p2 = self.float_positions[n2]
                s1 = SHAPE_CONFIGS[n1]["size"]
                s2 = SHAPE_CONFIGS[n2]["size"]
                c1x, c1y = p1[0] + s1/2, p1[1] + s1/2
                c2x, c2y = p2[0] + s2/2, p2[1] + s2/2
                
                dist = math.hypot(c1x - c2x, c1y - c2y)
                min_dist = (s1 + s2) / 2 * 0.95
                
                if dist < min_dist:
                    if p1[2] == 0 and p1[3] == 0 and p2[2] == 0 and p2[3] == 0:
                        continue
                    elif p1[2] == 0 and p1[3] == 0:
                        p2[2], p2[3] = -p2[2], -p2[3]
                        overlap = min_dist - dist
                        angle = math.atan2(c2y - c1y, c2x - c1x)
                        p2[0] += math.cos(angle) * overlap
                        p2[1] += math.sin(angle) * overlap
                    elif p2[2] == 0 and p2[3] == 0:
                        p1[2], p1[3] = -p1[2], -p1[3]
                        overlap = min_dist - dist
                        angle = math.atan2(c1y - c2y, c1x - c2x)
                        p1[0] += math.cos(angle) * overlap
                        p1[1] += math.sin(angle) * overlap
                    else:
                        p1[2], p2[2] = p2[2], p1[2]
                        p1[3], p2[3] = p2[3], p1[3]
                        overlap = min_dist - dist
                        angle = math.atan2(c2y - c1y, c2x - c1x)
                        p1[0] -= math.cos(angle) * overlap / 2
                        p1[1] -= math.sin(angle) * overlap / 2
                        p2[0] += math.cos(angle) * overlap / 2
                        p2[1] += math.sin(angle) * overlap / 2

        for number, pos in self.float_positions.items():
            if hasattr(self, "float_canvas_items") and number in self.float_canvas_items:
                self.grid_frame.coords(self.float_canvas_items[number], pos[0], pos[1])

        self.float_animation_job = self.root.after(20, self.float_animation_tick)

    def restore_grid_from_float(self) -> None:
        """Stop floating and snap buttons back to the normal grid layout."""
        self.stop_float_animation()
        for number in list(self.number_buttons.keys()):
            btn = self.number_buttons[number]
            btn.place_forget()
            # Restore normal button appearance
            btn.configure(
                relief="raised", bd=2, highlightthickness=1,
                padx=0, pady=0,
            )
        self.grid_frame.pack_propagate(True)
        self.grid_frame.grid_propagate(True)
        self.apply_grid_layout()
        self.update_button_faces()

    def get_rotated_positions(self, degrees: int) -> Dict[int, tuple[int, int]]:
        n = self.grid_size
        total = n * n
        base = {number: ((number - 1) // n, (number - 1) % n) for number in range(1, total + 1)}

        if degrees % 360 == 0:
            return base

        rotated = {}
        for number, (r, c) in base.items():
            if degrees % 360 == 90:
                nr, nc = c, (n - 1) - r
            elif degrees % 360 == 180:
                nr, nc = (n - 1) - r, (n - 1) - c
            elif degrees % 360 == 270:
                nr, nc = (n - 1) - c, r
            else:
                nr, nc = r, c
            rotated[number] = (nr, nc)
        return rotated

    def rotate_grid_90(self) -> None:
        self.rotation_degrees = (self.rotation_degrees + 90) % 360
        self.apply_grid_layout()

    def rotate_grid_180(self) -> None:
        self.rotation_degrees = (self.rotation_degrees + 180) % 360
        self.apply_grid_layout()

    def reset_grid_rotation(self) -> None:
        self.rotation_degrees = 0
        self.apply_grid_layout()

    def rebuild_grid_buttons(self) -> None:
        """Destroy all existing buttons and create new ones for the current grid_size."""
        for btn in self.number_buttons.values():
            btn.destroy()
        self.number_buttons.clear()

        total_cells = self.grid_size ** 2
        for number in range(1, total_cells + 1):
            button = tk.Button(
                self.grid_frame,
                text="",
                font=("Arial", 22, "bold"),
                width=5,
                height=2,
                bg="#ffffff",
                fg="#243447",
                activebackground="#dceffd",
                relief="raised",
                bd=2,
                command=lambda n=number: self.handle_cell_click(n),
            )
            self.number_buttons[number] = button
        self.apply_grid_layout()
        self.update_button_faces()

    def expand_grid_tier(self) -> None:
        """Expand the grid to the next tier (3x3 -> 4x4 -> 5x5). Grid category only."""
        if self.grid_tier_index >= len(GRID_TIERS) - 1:
            return  # Already at max tier
        self.grid_tier_index += 1
        self.grid_size = GRID_TIERS[self.grid_tier_index]
        self.levels_completed_in_tier = 0
        self.level_index = 1  # Reset levels for new grid tier
        self.consecutive_correct = 0
        self.rebuild_grid_buttons()
        self.message_text.set(
            f"Grid expanded to {self.grid_size}×{self.grid_size}! Levels reset. Keep going!"
        )

    def get_effective_mode(self) -> str:
        """Return the actual game mode, resolving 'mixed' to its current sub-mode."""
        mode_key = self.current_session.get("mode", "normal")
        if mode_key == "mixed":
            return self.current_active_mode
        return mode_key

    def is_letter_mode(self) -> bool:
        """Check if the current effective mode requires letter association."""
        return self.get_effective_mode() in {"letter_assoc", "letter_reverse"}

    def is_rotation_mode(self) -> bool:
        """Check if the current effective mode involves grid rotation."""
        return self.get_effective_mode() in {"rotate_90", "rotate_180", "reverse_rot90", "reverse_rot180"}

    def is_reverse_mode(self) -> bool:
        """Check if the current effective mode requires reverse order."""
        return self.get_effective_mode() in {"reverse", "reverse_rot90", "reverse_rot180", "letter_reverse"}

    def get_rotation_degrees_for_mode(self) -> int:
        """Return the rotation amount for the current mode."""
        mode = self.get_effective_mode()
        if mode in {"rotate_90", "reverse_rot90"}:
            return 90
        elif mode in {"rotate_180", "reverse_rot180"}:
            return 180
        return 0

    def build_top_stat(self, parent: tk.Widget, label: str, value_var: tk.StringVar) -> tk.Frame:
        frame = tk.Frame(parent, bg="#ffffff")
        tk.Label(frame, text=label, font=("Arial", 10), bg="#ffffff", fg="#4b5d73").pack()
        tk.Label(frame, textvariable=value_var, font=("Arial", 18, "bold"), bg="#ffffff", fg="#243447").pack(pady=(2, 0))
        return frame

    def build_side_panel(self, right: tk.Frame) -> None:
        how_to = self.make_card(right, "How to Play")
        self.pack_bullet(how_to, "1. Choose Grid or Objects category.")
        self.pack_bullet(how_to, "2. Choose a game type before starting.")
        self.pack_bullet(how_to, "3. Watch items light up one by one.")
        self.pack_bullet(how_to, "4. Normal: repeat same order.")
        self.pack_bullet(how_to, "5. Mental Reversal: answer in reverse order.")
        self.pack_bullet(how_to, "6. Grid Rotation 90°/180°: grid rotates before input.")
        self.pack_bullet(how_to, "7. Letter Association: click a cell, then type its letter.")
        self.pack_bullet(how_to, "8. Mixed: game type changes each level.")
        self.pack_bullet(how_to, "9. Get 5 correct in a row to level up.")
        self.pack_bullet(how_to, "10. Grid: grid grows after 5 levels.")
        self.pack_bullet(how_to, "11. Session lasts 4 minutes.")

        data_card = self.make_card(right, "Player Data")
        self.make_info_row(data_card, "Sessions Played", self.all_time_sessions_var)
        self.make_info_row(data_card, "Total Rounds", self.all_time_rounds_var)
        self.make_info_row(data_card, "Overall Accuracy", self.lifetime_accuracy_var)
        self.make_info_row(data_card, "Best Score", self.all_time_best_score_var)
        self.make_info_row(data_card, "Lifetime Avg Response", self.avg_response_var)
        self.make_info_row(data_card, "Total Lapse Time", self.lapse_total_var)
        self.make_info_row(data_card, "All-Time Progress Index", self.progress_index_var)
        tk.Label(
            data_card,
            text=f"Player data is stored permanently in\n{DATA_FILE}",
            font=("Arial", 9),
            bg="#ffffff",
            fg="#5c7288",
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        controls = self.make_card(right, "Data controls")
        ttk.Button(controls, text="Results Dashboard", command=self.open_results_with_password).pack(fill="x", pady=(0, 8))
        ttk.Button(controls, text="Delete Current Player Data", command=self.delete_current_player_data).pack(fill="x")

    def make_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid")
        card.pack(fill="x", pady=(0, 12))
        tk.Label(card, text=title, font=("Arial", 13, "bold"), bg="#ffffff", fg="#243447").pack(anchor="w", padx=12, pady=(12, 8))
        inner = tk.Frame(card, bg="#ffffff")
        inner.pack(fill="x", padx=12, pady=(0, 12))
        return inner

    def pack_bullet(self, parent: tk.Widget, text: str) -> None:
        tk.Label(parent, text=text, font=("Arial", 10), bg="#ffffff", fg="#36485c", anchor="w", justify="left", wraplength=320).pack(fill="x", pady=2)

    def make_info_row(self, parent: tk.Widget, label: str, value_var: tk.StringVar) -> None:
        row = tk.Frame(parent, bg="#ffffff")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Arial", 10), bg="#ffffff", fg="#5c7288").pack(side="left")
        tk.Label(row, textvariable=value_var, font=("Arial", 10, "bold"), bg="#ffffff", fg="#243447").pack(side="right")

    def only_digits_in_age(self, _event=None) -> None:
        cleaned = "".join(ch for ch in self.player_age_var.get() if ch.isdigit())
        if cleaned != self.player_age_var.get():
            self.player_age_var.set(cleaned)

    def load_store(self) -> Dict[str, object]:
        if not os.path.exists(DATA_FILE):
            return {"players": {}, "last_player_key": ""}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                return {"players": {}, "last_player_key": ""}
            data.setdefault("players", {})
            data.setdefault("last_player_key", "")
            return data
        except (json.JSONDecodeError, OSError):
            return {"players": {}, "last_player_key": ""}

    def save_store(self) -> None:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(self.player_store, file, indent=2)

    def empty_session_stats(self) -> Dict[str, object]:
        return {
            "started_at": "",
            "rounds_played": 0,
            "rounds_correct": 0,
            "response_times_ms": [],
            "lapse_count": 0,
            "total_lapse_duration_ms": 0,
            "longest_lapse_ms": 0,
            "lapses": [],
            "level_history": [],
            "game_duration_ms": 0,
            "mode": "",
            "category": "numbers",
            "highest_level_reached": 1,
        }

    def create_empty_player(self, name: str, age: str) -> Dict[str, object]:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        return {
            "name": name,
            "age": age,
            "created_at": now,
            "updated_at": now,
            "lifetime": {
                "rounds_played": 0,
                "rounds_correct": 0,
                "total_game_duration_ms": 0,
                "total_response_time_ms": 0,
                "average_response_time_ms": 0,
                "total_lapse_count": 0,
                "total_lapse_duration_ms": 0,
                "average_lapse_duration_ms": 0,
                "longest_lapse_ms": 0,
                "progress_index_ms": None,
                "sessions_played": 0,
                "best_score": 0,
            },
            "sessions": [],
            "mode_progress": {},
        }

    def normalize_player_key(self, name: str, age: str) -> str:
        return f"{name.strip().lower()}__{age.strip()}"

    def mode_progress_key(self, category_key: str, mode_key: str) -> str:
        return f"{category_key}:{mode_key}"

    def get_saved_mode_progress(self, player: Dict[str, object], category_key: str, mode_key: str) -> Dict[str, int]:
        progress = player.get("mode_progress", {})
        if not isinstance(progress, dict):
            return {}
        saved = progress.get(self.mode_progress_key(category_key, mode_key), {})
        return saved if isinstance(saved, dict) else {}

    def apply_saved_mode_progress(self, player: Dict[str, object], category_key: str, mode_key: str) -> None:
        saved = self.get_saved_mode_progress(player, category_key, mode_key)
        self.level_index = max(1, min(int(saved.get("level_index", 1)), len(LEVELS) - 1))
        self.grid_tier_index = max(0, min(int(saved.get("grid_tier_index", 0)), len(GRID_TIERS) - 1))
        self.grid_size = GRID_TIERS[self.grid_tier_index]
        if category_key != "numbers":
            self.grid_tier_index = 0
            self.grid_size = GRID_TIERS[0]
        self.levels_completed_in_tier = max(0, min(int(saved.get("levels_completed_in_tier", 0)), LEVELS_PER_GRID_TIER - 1))

    def save_mode_progress_for_player(self, player: Dict[str, object], category_key: str, mode_key: str) -> None:
        progress = player.setdefault("mode_progress", {})
        if not isinstance(progress, dict):
            progress = {}
            player["mode_progress"] = progress
        progress[self.mode_progress_key(category_key, mode_key)] = {
            "level_index": self.level_index,
            "level": LEVELS[self.level_index]["level"],
            "grid_tier_index": self.grid_tier_index if category_key == "numbers" else 0,
            "grid_size": self.grid_size if category_key == "numbers" else GRID_TIERS[0],
            "levels_completed_in_tier": self.levels_completed_in_tier if category_key == "numbers" else 0,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def load_last_player(self) -> None:
        key = self.player_store.get("last_player_key", "")
        player = self.player_store.get("players", {}).get(key)
        if not player:
            return
        self.active_player_key = key
        self.active_player = player
        self.player_name_var.set(str(player.get("name", "")))
        self.player_age_var.set(str(player.get("age", "")))
        self.best_score = int(player.get("lifetime", {}).get("best_score", 0))
        self.current_player_var.set(f"Current player: {player.get('name', '')}, age {player.get('age', '')}")
        self.on_mode_change()
        self.refresh_stats_display()

    def calculate_accuracy(self, correct: int, total: int) -> int:
        return round((correct / total) * 100) if total else 0

    def format_seconds(self, ms: int) -> str:
        return f"{ms / 1000:.1f}s"

    def calculate_progress_index_ms(self, total_time_ms: int, total_lapse_ms: int, correct_responses: int) -> Optional[float]:
        if correct_responses <= 0:
            return None
        active_time_ms = max(total_time_ms - total_lapse_ms, 0)
        return active_time_ms / correct_responses

    def format_progress_index(self, progress_index_ms: Optional[float]) -> str:
        if progress_index_ms is None:
            return "N/A"
        return f"{progress_index_ms / 1000:.1f}s/correct"

    def format_duration_compact(self, ms: int) -> str:
        seconds = max(ms, 0) / 1000
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        remaining = int(seconds % 60)
        return f"{minutes}m {remaining:02d}s"

    def get_continuous_lapse_durations(self, lapses: List[Dict[str, object]]) -> List[float]:
        intervals = []
        fallback_durations = []
        for lapse in lapses:
            duration_ms = int(lapse.get("duration_ms", 0))
            if duration_ms <= 0:
                continue
            try:
                start_struct = time.strptime(str(lapse.get("started_at", "")), "%Y-%m-%dT%H:%M:%S")
                start_ms = int(time.mktime(start_struct) * 1000)
                intervals.append((start_ms, start_ms + duration_ms))
            except (TypeError, ValueError, OverflowError):
                fallback_durations.append(duration_ms / 1000)

        if not intervals:
            return fallback_durations

        intervals.sort()
        merged = []
        current_start, current_end = intervals[0]
        for start_ms, end_ms in intervals[1:]:
            if start_ms <= current_end + 1500:
                current_end = max(current_end, end_ms)
            else:
                merged.append((current_start, current_end))
                current_start, current_end = start_ms, end_ms
        merged.append((current_start, current_end))

        return [(end_ms - start_ms) / 1000 for start_ms, end_ms in merged] + fallback_durations

    def summarize_sessions(self, sessions: List[Dict[str, object]]) -> Dict[str, object]:
        total_sessions = len(sessions)
        total_rounds = sum(int(session.get("rounds_played", 0)) for session in sessions)
        total_correct = sum(int(session.get("rounds_correct", 0)) for session in sessions)
        total_response_time = sum(int(session.get("total_response_time_ms", 0)) for session in sessions)
        total_lapse_time = sum(int(session.get("total_lapse_duration_ms", 0)) for session in sessions)
        total_game_time = sum(int(session.get("game_duration_ms", 0)) for session in sessions)
        best_score = max((int(session.get("score", 0)) for session in sessions), default=0)
        avg_response_ms = round(total_response_time / total_rounds) if total_rounds else 0
        progress_index_ms = self.calculate_progress_index_ms(total_game_time, total_lapse_time, total_correct)
        return {
            "sessions": total_sessions,
            "rounds": total_rounds,
            "correct": total_correct,
            "accuracy": self.calculate_accuracy(total_correct, total_rounds),
            "best_score": best_score,
            "avg_response_ms": avg_response_ms,
            "total_lapse_ms": total_lapse_time,
            "progress_index_ms": progress_index_ms,
        }

    def format_metric_summary_line(self, label: str, summary: Dict[str, object]) -> str:
        return (
            f"{label}: "
            f"Sessions Played: {summary['sessions']}  |  "
            f"Total Rounds: {summary['rounds']}  |  "
            f"Overall Accuracy: {summary['accuracy']}%  |  "
            f"Best Score: {summary['best_score']}  |  "
            f"Avg Response: {self.format_seconds(int(summary['avg_response_ms']))}  |  "
            f"Total Lapse Time: {self.format_duration_compact(int(summary['total_lapse_ms']))}  |  "
            f"Progress Index: {self.format_progress_index(summary['progress_index_ms'])}"
        )

    def refresh_post_game_summary(self) -> None:
        if not self.active_player:
            self.post_game_summary_var.set("")
            return
        sessions = list(self.active_player.get("sessions", []))
        if not sessions:
            self.post_game_summary_var.set("")
            return
        today = time.strftime("%Y-%m-%d")
        today_sessions = [
            session for session in sessions
            if str(session.get("ended_at") or session.get("started_at", "")).startswith(today)
        ]
        today_summary = self.summarize_sessions(today_sessions)
        overall_summary = self.summarize_sessions(sessions)
        self.post_game_summary_var.set(
            "Latest Results\n"
            f"{self.format_metric_summary_line('Today', today_summary)}\n"
            f"{self.format_metric_summary_line('Overall', overall_summary)}"
        )

    def refresh_stats_display(self) -> None:
        if self.started:
            current_level = LEVELS[self.level_index]["level"]
        else:
            current_level = int(self.current_session.get("highest_level_reached", 1))

        # Show level with grid info for the Grid category.
        is_objects = self.game_category_var.get() == "objects"
        if not is_objects and self.grid_size > 3 and self.started:
            self.level_value_var.set(f"{current_level} ({self.grid_size}×{self.grid_size})")
        else:
            self.level_value_var.set(str(current_level))
        self.score_value_var.set(str(self.score))
        self.best_value_var.set(str(self.best_score))
        self.progress_var.set(int(((self.level_index + 1) / len(LEVELS)) * 100) if self.started else 0)
        self.stars_var.set(str(self.stars))
        self.lives_var.set(" ".join("❤" if i < self.lives else "♡" for i in range(3)))

        if self.active_player:
            overall_summary = self.summarize_sessions(list(self.active_player.get("sessions", [])))
            self.all_time_sessions_var.set(str(overall_summary["sessions"]))
            self.all_time_rounds_var.set(str(overall_summary["rounds"]))
            self.lifetime_accuracy_var.set(f"{overall_summary['accuracy']}%")
            self.all_time_best_score_var.set(str(overall_summary["best_score"]))
            self.avg_response_var.set(self.format_seconds(int(overall_summary["avg_response_ms"])))
            self.lapse_total_var.set(self.format_duration_compact(int(overall_summary["total_lapse_ms"])))
            self.progress_index_var.set(self.format_progress_index(overall_summary["progress_index_ms"]))
        else:
            self.all_time_sessions_var.set("0")
            self.all_time_rounds_var.set("0")
            self.lifetime_accuracy_var.set("0%")
            self.all_time_best_score_var.set("0")
            self.avg_response_var.set("0.0s")
            self.lapse_total_var.set("0.0s")
            self.progress_index_var.set("N/A")
        self.on_mode_change()

    def record_app_activity(self, _event=None) -> None:
        now_ms = int(time.time() * 1000)
        if self.current_idle_lapse_start_ms is not None:
            duration_ms = now_ms - self.current_idle_lapse_start_ms
            self.record_lapse(self.current_idle_lapse_start_ms, duration_ms, "no_input_idle")
            self.current_idle_lapse_start_ms = None
        self.last_app_activity_ms = now_ms

    def start_global_lapse_watch(self) -> None:
        self.stop_global_lapse_watch()
        self.global_lapse_watch_job = self.root.after(500, self.check_global_idle_lapse)

    def stop_global_lapse_watch(self) -> None:
        if self.global_lapse_watch_job is not None:
            try:
                self.root.after_cancel(self.global_lapse_watch_job)
            except tk.TclError:
                pass
            self.global_lapse_watch_job = None

    def check_global_idle_lapse(self) -> None:
        now_ms = int(time.time() * 1000)
        idle_ms = now_ms - self.last_app_activity_ms

        if idle_ms >= LAPSE_THRESHOLD_MS and self.current_idle_lapse_start_ms is None:
            self.current_idle_lapse_start_ms = self.last_app_activity_ms

        self.global_lapse_watch_job = self.root.after(500, self.check_global_idle_lapse)

    def record_lapse(self, start_ms: int, duration_ms: int, trigger: str) -> None:
        if duration_ms <= 0:
            return
        started_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start_ms / 1000))
        lapse = LapseEntry(started_at=started_at, duration_ms=duration_ms, trigger=trigger)
        self.current_session["lapses"].append(asdict(lapse))
        self.current_session["lapse_count"] += 1
        self.current_session["total_lapse_duration_ms"] += duration_ms
        self.current_session["longest_lapse_ms"] = max(int(self.current_session["longest_lapse_ms"]), duration_ms)
        self.refresh_stats_display()

    def handle_start_game(self) -> None:
        name = self.player_name_var.get().strip()
        age = self.player_age_var.get().strip()
        mode_key = self.game_mode_var.get()
        cat_key = self.game_category_var.get()

        if not name or not age:
            self.message_text.set("Please enter player name and age first.")
            return

        key = self.normalize_player_key(name, age)
        players = self.player_store.setdefault("players", {})
        if key not in players:
            players[key] = self.create_empty_player(name, age)
        else:
            players[key]["name"] = name
            players[key]["age"] = age
            players[key]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            players[key].setdefault("mode_progress", {})

        self.player_store["last_player_key"] = key
        self.active_player_key = key
        self.active_player = players[key]
        self.save_store()

        self.started = True
        self.phase = "idle"
        self.score = 0
        self.stars = 0
        self.lives = 3
        self.best_score = int(self.active_player.get("lifetime", {}).get("best_score", 0))
        self.current_player_var.set(f"Current player: {name}, age {age}")

        # Progression system reset
        self.consecutive_correct = 0
        self.recovery_mode = False
        self.recovery_target_level = 0

        self.apply_saved_mode_progress(self.active_player, cat_key, mode_key)
        if cat_key == "numbers":
            self.rebuild_grid_buttons()

        # Letter association reset
        self.letter_assignments = {}
        self.waiting_for_letter = False
        self.letter_step_index = 0

        self.feedback_var.set("")
        self.current_submode_var.set("")
        self.post_game_summary_var.set("")

        # Mixed mode: pick first sub-mode
        if mode_key == "mixed":
            self.current_active_mode = random.choice(MIXED_MODE_POOL)
        else:
            self.current_active_mode = mode_key

        # Bind keyboard for letter association
        self.root.bind("<Key>", self.on_key_press)

        self.current_session = self.empty_session_stats()
        self.current_session["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.current_session["mode"] = mode_key
        self.current_session["category"] = cat_key
        self.current_session["starting_level"] = LEVELS[self.level_index]["level"]
        self.current_session["highest_level_reached"] = LEVELS[self.level_index]["level"]
        self.pending_persisted = False
        self.session_start_ms = int(time.time() * 1000)
        self.stop_after_round = False
        self.reset_grid_rotation()
        self.update_button_faces()
        cat_label = GAME_CATEGORIES.get(cat_key, cat_key)
        mode_label = GAME_MODES.get(mode_key, mode_key)
        if mode_key == "mixed":
            sub_label = GAME_MODES.get(self.current_active_mode, self.current_active_mode)
            self.message_text.set(f"Get ready! {cat_label} — Mixed [{sub_label}]")
        else:
            self.message_text.set(f"Get ready! {cat_label} — {mode_label}")
        self.refresh_stats_display()
        self.record_app_activity()
        self.start_session_timer()
        self.start_round(self.level_index)

    def start_session_timer(self) -> None:
        self.stop_session_timer()
        self.session_timer_job = self.root.after(250, self.update_session_timer)

    def stop_session_timer(self) -> None:
        if self.session_timer_job is not None:
            try:
                self.root.after_cancel(self.session_timer_job)
            except tk.TclError:
                pass
            self.session_timer_job = None

    def update_session_timer(self) -> None:
        if not self.started or self.session_start_ms is None:
            self.session_timer_job = None
            return

        elapsed_ms = int(time.time() * 1000) - self.session_start_ms
        remaining_ms = max(GAME_DURATION_MS - elapsed_ms, 0)
        minutes = remaining_ms // 60000
        seconds = (remaining_ms % 60000) // 1000
        self.timer_text.set(f"Time left: {minutes:02d}:{seconds:02d}")

        if elapsed_ms >= GAME_DURATION_MS:
            self.stop_after_round = True
            if self.phase in {"idle", "result"}:
                self.finish_game_due_to_time()
                self.session_timer_job = None
                return

        self.session_timer_job = self.root.after(250, self.update_session_timer)

    def start_round(self, new_level_index: Optional[int] = None) -> None:
        if new_level_index is not None:
            self.level_index = min(new_level_index, len(LEVELS) - 1)

        self.cancel_jobs()
        self.reset_grid_rotation()
        current_level = LEVELS[self.level_index]
        is_objects = self.game_category_var.get() == "objects"
        total_cells = 9 if is_objects else self.grid_size ** 2
        count = min(current_level["count"], total_cells)
        self.sequence = random.sample(list(range(1, total_cells + 1)), count)
        self.selected = []
        self.round_input_start_ms = None
        self.waiting_for_letter = False
        self.letter_step_index = 0
        self.phase = "show_sequence"

        # Mixed mode: pick sub-mode for each new level
        mode_key = self.current_session.get("mode", "normal")
        if mode_key == "mixed":
            self.current_active_mode = random.choice(MIXED_MODE_POOL)

        # Generate letter assignments for letter modes
        if self.is_letter_mode():
            letters = random.sample(LETTER_POOL, count)
            self.letter_assignments = {self.sequence[i]: letters[i] for i in range(count)}
        else:
            self.letter_assignments = {}

        # Build message
        item_word = "object(s)" if is_objects else "cell(s)"
        effective = self.get_effective_mode()
        effective_label = GAME_MODES.get(effective, effective)
        trial_info = f" (Trial {self.consecutive_correct + 1}/{TRIALS_TO_RECOVER if self.recovery_mode else TRIALS_TO_ADVANCE})"
        if mode_key == "mixed":
            mode_display = f"Mixed [{effective_label}]"
            self.current_submode_var.set(f"Current Submode: {effective_label}")
        else:
            mode_display = effective_label
            self.current_submode_var.set(f"Current Mode: {effective_label}")

        grid_info = ""
        if not is_objects and self.grid_size > 3:
            grid_info = f" [{self.grid_size}×{self.grid_size} grid]"

        self.message_text.set(
            f"Watch {count} {item_word} light up. {mode_display}{grid_info}{trial_info}"
        )
        self.refresh_grid_appearance()
        self.refresh_stats_display()

        # In objects mode, start floating animation during sequence display
        if is_objects:
            self.update_button_faces()
            self.start_float_animation()

        self.show_sequence_step(0)

    def animate_grid_rotation(self, degrees: int, item_word: str) -> None:
        self.grid_frame.update_idletasks()
        w = self.grid_frame.winfo_width()
        h = self.grid_frame.winfo_height()
        self.grid_frame.configure(width=w, height=h)
        self.grid_frame.grid_propagate(False)
        
        cx = w / 2
        cy = h / 2
        
        boxes = []
        for number, btn in self.number_buttons.items():
            bx = btn.winfo_x()
            by = btn.winfo_y()
            bw = btn.winfo_width()
            bh = btn.winfo_height()
            
            corners = [
                (bx - cx, by - cy),
                (bx + bw - cx, by - cy),
                (bx + bw - cx, by + bh - cy),
                (bx - cx, by + bh - cy)
            ]
            
            text = btn.cget("text")
            fg = btn.cget("fg")
            boxes.append((corners, text, fg))
            btn.grid_forget()

        canvas_items = []
        for corners, text, fg in boxes:
            poly = self.grid_frame.create_polygon(0,0,0,0,0,0,0,0, fill="#ffffff", outline="#cccccc", width=2)
            txt = self.grid_frame.create_text(0,0, text=text, font=("Arial", 22, "bold"), fill=fg)
            canvas_items.append((poly, txt, corners))
            
        steps = 20
        delay = 20
        rad_step = math.radians(degrees) / steps
        
        def step_anim(step):
            if step > steps:
                for poly, txt, _ in canvas_items:
                    self.grid_frame.delete(poly)
                    self.grid_frame.delete(txt)
                self.rotation_degrees = (self.rotation_degrees + degrees) % 360
                self.grid_frame.grid_propagate(True)
                self.apply_grid_layout()
                if self.is_reverse_mode():
                    self.message_text.set(f"Grid rotated {degrees}°. Click the {item_word} in reverse order.")
                else:
                    self.message_text.set(f"Grid rotated {degrees}°. Click the {item_word} in the same order.")
                self.next_round_job = self.root.after(700, self.enter_input_phase)
                return
            
            angle = rad_step * step
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            
            for poly, txt, corners in canvas_items:
                rotated_coords = []
                for (x, y) in corners:
                    rx = x * cos_a - y * sin_a
                    ry = x * sin_a + y * cos_a
                    rotated_coords.extend([cx + rx, cy + ry])
                self.grid_frame.coords(poly, *rotated_coords)
                
                tx = sum(c[0] for c in corners) / 4
                ty = sum(c[1] for c in corners) / 4
                rtx = tx * cos_a - ty * sin_a
                rty = tx * sin_a + ty * cos_a
                self.grid_frame.coords(txt, cx + rtx, cy + rty)
                
            self.root.after(delay, lambda: step_anim(step + 1))
            
        step_anim(1)

    def show_sequence_step(self, index: int) -> None:
        if self.phase != "show_sequence":
            return

        if index >= len(self.sequence):
            is_objects = self.game_category_var.get() == "objects"
            # Extra 1s breathing time for objects mode after the last highlight
            extra_delay = 1000 if is_objects else 0
            rot_degrees = self.get_rotation_degrees_for_mode()

            if rot_degrees > 0:
                self.phase = "rotate_pause"
                item_word = "objects" if is_objects else "cells"
                def do_rotate_then_input():
                    self.animate_grid_rotation(rot_degrees, item_word)
                self.next_round_job = self.root.after(extra_delay, do_rotate_then_input)
            else:
                if extra_delay:
                    self.next_round_job = self.root.after(extra_delay, self.enter_input_phase)
                else:
                    self.enter_input_phase()
            return

        number = self.sequence[index]
        self.highlight_single_cell(number)

        # In letter modes, also show the letter on the button briefly
        if self.is_letter_mode() and number in self.letter_assignments:
            letter = self.letter_assignments[number]
            btn = self.number_buttons.get(number)
            if btn and not self.floating_active:
                btn.configure(text=letter, fg="#b8860b")

        show_ms = int(LEVELS[self.level_index]["show_ms"])
        self.show_job = self.root.after(show_ms, lambda: self.clear_highlight_then_continue(index))

    def enter_input_phase(self) -> None:
        # For objects mode, keep floating — don't restore grid
        self.phase = "input"
        self.round_input_start_ms = int(time.time() * 1000)

        is_objects = self.game_category_var.get() == "objects"
        item_word = "objects" if is_objects else "cells"
        effective = self.get_effective_mode()

        if self.is_letter_mode():
            if self.is_reverse_mode():
                msg = f"Click each {item_word[:-2]} then type its letter — in REVERSE order."
            else:
                msg = f"Click each {item_word[:-2]} then type its letter — in order."
        elif self.is_reverse_mode():
            if self.is_rotation_mode():
                msg = f"Grid rotated. Click the {item_word} in reverse order."
            else:
                msg = f"Click the {item_word} in reverse order."
        elif self.is_rotation_mode():
            msg = f"Grid rotated. Click the {item_word} in the same order."
        else:
            msg = f"Now click the {item_word} in the same order."

        self.message_text.set(msg)
        self.refresh_grid_appearance()

    def clear_highlight_then_continue(self, index: int) -> None:
        if self.phase != "show_sequence":
            return
        # Clear letter text from button after highlight
        number = self.sequence[index] if index < len(self.sequence) else None
        if number and number in self.number_buttons and not self.floating_active:
            self.number_buttons[number].configure(text="")
        self.refresh_grid_appearance()
        gap_ms = int(LEVELS[self.level_index]["gap_ms"])
        self.show_job = self.root.after(gap_ms, lambda: self.show_sequence_step(index + 1))

    def highlight_single_cell(self, number: int) -> None:
        self.refresh_grid_appearance()
        btn = self.number_buttons.get(number)
        if not btn:
            return
        if self.floating_active and self.shape_highlight_images:
            # Update canvas image
            if hasattr(self, "float_canvas_items") and number in self.float_canvas_items:
                self.grid_frame.itemconfig(self.float_canvas_items[number], image=self.shape_highlight_images[number])
        elif self.game_category_var.get() == "objects" and self.shape_highlight_images:
            btn.configure(image=self.shape_highlight_images[number])
        else:
            btn.configure(bg="#ffe58f", activebackground="#ffe58f")

    def on_canvas_click(self, event) -> None:
        if self.phase != "input" or not self.floating_active:
            return
        if self.waiting_for_letter:
            return  # Waiting for keyboard input, ignore clicks
        items = self.grid_frame.find_overlapping(event.x, event.y, event.x, event.y)
        for item_id in reversed(items):
            number = next((n for n, i_id in getattr(self, 'float_canvas_items', {}).items() if i_id == item_id), None)
            if number is not None:
                x, y = self.grid_frame.coords(item_id)
                img_x, img_y = int(event.x - x), int(event.y - y)
                pil_img = getattr(self, "shape_pil_images", {}).get(number)
                if pil_img and 0 <= img_x < pil_img.width and 0 <= img_y < pil_img.height:
                    r, g, b, a = pil_img.getpixel((img_x, img_y))
                    if a > 0:
                        self.handle_cell_click(number)
                        return

    def on_key_press(self, event) -> None:
        """Handle keyboard input for letter association mode."""
        if not self.waiting_for_letter or self.phase != "input":
            return
        typed = event.char.upper()
        if not typed or not typed.isalpha():
            return

        self.record_app_activity()
        expected_seq = self.get_expected_sequence()
        step = self.letter_step_index
        if step >= len(expected_seq):
            return

        expected_cell = expected_seq[step]
        expected_letter = self.letter_assignments.get(expected_cell, "")

        self.waiting_for_letter = False

        if typed == expected_letter:
            # Correct letter — move to next cell in sequence
            btn = self.number_buttons.get(expected_cell)
            if btn and not self.floating_active:
                btn.configure(text=expected_letter, fg="#b8860b")
            self.letter_step_index += 1
            if self.letter_step_index >= len(expected_seq):
                # All cells and letters correct
                self.evaluate_attempt(self.selected[:])
            else:
                self.message_text.set(f"✓ Correct letter! Now click the next cell. ({self.letter_step_index + 1}/{len(expected_seq)})")
        else:
            # Wrong letter — immediately fail the attempt
            self.selected.append(-1)  # Mark as wrong
            self.evaluate_attempt(self.selected[:])

    def get_expected_sequence(self) -> List[int]:
        if self.is_reverse_mode():
            return list(reversed(self.sequence))
        return self.sequence[:]

    def handle_cell_click(self, number: int) -> None:
        if self.phase != "input":
            return
        if self.waiting_for_letter:
            return  # Must type letter first
        if number in self.selected:
            return

        self.record_app_activity()
        self.selected.append(number)
        self.refresh_grid_appearance()

        expected_seq = self.get_expected_sequence()
        step_index = len(self.selected) - 1

        # Check if this click is correct so far (early termination on wrong click)
        if self.selected[step_index] != expected_seq[step_index]:
            # Wrong cell — fail immediately
            self.evaluate_attempt(self.selected[:])
            return

        # Letter association mode: after correct cell click, wait for letter
        if self.is_letter_mode():
            self.waiting_for_letter = True
            self.letter_step_index = step_index
            expected_cell = expected_seq[step_index]
            self.message_text.set(f"Good! Now type the letter for this cell. ({step_index + 1}/{len(expected_seq)})")
            return

        # Check if all cells selected
        current_level = LEVELS[self.level_index]
        count = min(current_level["count"], self.grid_size ** 2 if self.game_category_var.get() != "objects" else 9)
        if len(self.selected) == count:
            self.evaluate_attempt(self.selected[:])

    def evaluate_attempt(self, attempt: List[int]) -> None:
        response_time_ms = 0
        if self.round_input_start_ms is not None:
            response_time_ms = int(time.time() * 1000) - self.round_input_start_ms

        expected = self.get_expected_sequence()
        correct = attempt == expected
        level_number = LEVELS[self.level_index]["level"]
        effective_mode = self.get_effective_mode()
        base_mode = self.current_session.get("mode", "normal")

        self.current_session["rounds_played"] += 1
        self.current_session["rounds_correct"] += 1 if correct else 0
        self.current_session["response_times_ms"].append(response_time_ms)
        self.current_session["highest_level_reached"] = max(
            int(self.current_session.get("highest_level_reached", 1)),
            LEVELS[self.level_index]["level"],
        )

        self.current_session["level_history"].append({
            "level": level_number,
            "correct": correct,
            "response_time_ms": response_time_ms,
            "sequence_length": len(self.sequence),
            "mode": base_mode,
            "effective_mode": effective_mode,
            "game_type_label": GAME_MODES.get(effective_mode, effective_mode),
            "expected_sequence": expected[:],
            "shown_sequence": self.sequence[:],
            "player_sequence": attempt[:],
            "grid_rotation_degrees": self.rotation_degrees,
            "grid_size": self.grid_size,
            "consecutive_correct_before": self.consecutive_correct,
        })

        self.phase = "result"

        if correct:
            points = int(LEVELS[self.level_index]["count"]) * 10
            self.score += points
            self.stars += 1
        else:
            self.lives -= 1

        self.refresh_stats_display()
        self.refresh_grid_appearance()

        if self.lives <= 0:
            self.message_text.set(f"Game over. Correct order was {', '.join(map(str, expected))}.")
            self.finish_game()
            return

        self.handle_round_completion(correct)

    def show_popup_message(self, msg: str, fg_color: str) -> None:
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes('-topmost', True)
        
        popup.configure(bg="#ffffff", bd=3, relief="solid")
        label = tk.Label(popup, text=msg, font=("Arial", 14, "bold"), fg=fg_color, bg="#ffffff", justify="center")
        label.pack(expand=True, fill="both", padx=20, pady=20)
        
        popup.update_idletasks()
        w = popup.winfo_reqwidth()
        h = popup.winfo_reqheight()
        
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (w // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        
        self.root.after(1500, popup.destroy)

    def handle_round_completion(self, correct: bool) -> None:
        current_level_number = LEVELS[self.level_index]["level"]
        is_objects = self.game_category_var.get() == "objects"

        if self.stop_after_round:
            self.finish_game_due_to_time()
            return

        if correct:
            self.consecutive_correct += 1
            required = TRIALS_TO_RECOVER if self.recovery_mode else TRIALS_TO_ADVANCE

            motivational_messages = ["Great job!", "Keep it up!", "Awesome!", "Spot on!", "Excellent!"]
            self.show_popup_message(f"{random.choice(motivational_messages)}\nSequence was correct.", "#28a745")

            if self.consecutive_correct >= required:
                # Completed enough consecutive correct trials
                if self.recovery_mode:
                    # Recovery complete — return to the level we fell from
                    self.recovery_mode = False
                    target = self.recovery_target_level
                    self.recovery_target_level = 0
                    self.consecutive_correct = 0
                    # Go back to the target level
                    self.level_index = min(target, len(LEVELS) - 1)
                    self.message_text.set(
                        f"Recovery complete! Back to level {LEVELS[self.level_index]['level']}."
                    )
                else:
                    # Advance to next level
                    self.consecutive_correct = 0

                    if self.level_index < len(LEVELS) - 1:
                        self.level_index += 1
                        self.levels_completed_in_tier += 1
                        self.current_session["highest_level_reached"] = max(
                            int(self.current_session["highest_level_reached"]),
                            LEVELS[self.level_index]["level"],
                        )

                        # Check grid expansion for the Grid category.
                        if not is_objects and self.levels_completed_in_tier >= LEVELS_PER_GRID_TIER:
                            if self.grid_tier_index < len(GRID_TIERS) - 1:
                                self.next_round_job = self.root.after(1500, self._do_grid_expand)
                                return

                        next_level = LEVELS[self.level_index]["level"]
                        self.message_text.set(
                            f"Level {current_level_number} cleared! Moving to level {next_level}."
                        )
                    else:
                        self.message_text.set(
                            f"Amazing! Max level reached. Continuing at level {current_level_number}."
                        )
            else:
                self.message_text.set(
                    f"✓ Correct! ({self.consecutive_correct}/{required} for {'recovery' if self.recovery_mode else 'next level'})"
                )

            self.next_round_job = self.root.after(1500, lambda: self.start_round(self.level_index))
            self.refresh_stats_display()
            return

        # ── Incorrect ──
        trial_position = self.consecutive_correct + 1  # Which trial in the streak failed
        self.consecutive_correct = 0

        if trial_position >= 3:
            # Mistake on trial 3, 4, or 5 → restart same level
            self.message_text.set(
                f"Mistake on trial {trial_position}. Restarting level {current_level_number}."
            )
            self.show_popup_message(
                f"Incorrect sequence.\n\nReason: You clicked the wrong cell.\nNext step: Restarting level {current_level_number}.",
                "#d9534f"
            )
        else:
            # Mistake on trial 1 or 2 → demote level
            min_level = 1  # Minimum level index
            if self.recovery_mode:
                # Already in recovery — demote further, update recovery target
                self.recovery_target_level = self.level_index
            else:
                # Enter recovery mode
                self.recovery_mode = True
                self.recovery_target_level = self.level_index

            # Demote by 1 level (but not below min)
            if self.level_index > min_level:
                self.level_index -= 1

            demoted_level = LEVELS[self.level_index]["level"]
            self.message_text.set(
                f"Mistake on trial {trial_position}. Dropped to level {demoted_level}. "
                f"Get {TRIALS_TO_RECOVER} correct to recover."
            )
            self.show_popup_message(
                f"Incorrect sequence.\n\nReason: You clicked the wrong cell.\nNext step: Dropped to level {demoted_level}.\nComplete {TRIALS_TO_RECOVER} correct trials to recover.",
                "#d9534f"
            )

        self.next_round_job = self.root.after(1500, lambda: self.start_round(self.level_index))

    def _do_grid_expand(self) -> None:
        """Callback to expand grid after delay."""
        self.expand_grid_tier()
        self.next_round_job = self.root.after(2000, lambda: self.start_round(self.level_index))

    def finish_game_due_to_time(self) -> None:
        self.message_text.set("4 minutes completed. Saving results now.")
        self.finish_game()

    def finish_game(self) -> None:
        if self.pending_persisted:
            return
        if self.current_idle_lapse_start_ms is not None:
            now_ms = int(time.time() * 1000)
            duration_ms = now_ms - self.current_idle_lapse_start_ms
            self.record_lapse(self.current_idle_lapse_start_ms, duration_ms, "no_input_idle")
            self.current_idle_lapse_start_ms = None
        if self.session_start_ms is not None:
            self.current_session["game_duration_ms"] = int(time.time() * 1000) - self.session_start_ms

        self.started = False
        self.phase = "finished"
        self.stop_session_timer()
        self.cancel_jobs()

        # Restore grid layout if objects were floating
        if self.game_category_var.get() == "objects":
            self.restore_grid_from_float()

        self.timer_text.set("")

        self.persist_session_data(self.score)
        self.pending_persisted = True
        self.refresh_stats_display()

    def refresh_grid_appearance(self) -> None:
        cat = self.game_category_var.get()
        is_floating = self.floating_active
        for number, button in self.number_buttons.items():
            bg = "#ffffff"
            active_bg = "#dceffd"
            fg = "#243447"

            # Clear text for non-objects mode if not selected to remove old letters
            if cat != "objects" and number not in self.selected:
                button.configure(text="")

            if number in self.selected:
                bg = "#ffcc80"
                active_bg = "#ffcc80"
            elif not self.reduced_distraction.get():
                bg = "#fef4f7"
                active_bg = "#fff1c7"

            if cat == "objects" and self.shape_photo_images:
                if is_floating:
                    # During floating: update canvas item image
                    if hasattr(self, "float_canvas_items") and number in self.float_canvas_items:
                        item_id = self.float_canvas_items[number]
                        if number in self.selected:
                            self.grid_frame.itemconfig(item_id, image=self.shape_selected_images.get(number, ""))
                        else:
                            self.grid_frame.itemconfig(item_id, image=self.shape_photo_images.get(number, ""))
                else:
                    # Static grid mode for objects
                    if number in self.selected:
                        button.configure(bg=bg, activebackground=active_bg, fg=fg, state="normal", image=self.shape_selected_images.get(number, ""))
                    else:
                        button.configure(bg=bg, activebackground=active_bg, fg=fg, state="normal", image=self.shape_photo_images.get(number, ""))
            else:
                button.configure(bg=bg, activebackground=active_bg, fg=fg, state="normal")

    def persist_session_data(self, final_score: int) -> None:
        if not self.active_player_key:
            return
        players = self.player_store.setdefault("players", {})
        player = players.get(self.active_player_key)
        if not player:
            return

        rounds_played = int(self.current_session["rounds_played"])
        rounds_correct = int(self.current_session["rounds_correct"])
        response_times = list(self.current_session["response_times_ms"])
        total_response_time = int(sum(response_times))
        avg_response_time = round(total_response_time / len(response_times)) if response_times else 0
        lapse_count = int(self.current_session["lapse_count"])
        total_lapse_duration = int(self.current_session["total_lapse_duration_ms"])
        avg_lapse_duration = round(total_lapse_duration / lapse_count) if lapse_count else 0
        longest_lapse = int(self.current_session["longest_lapse_ms"])
        game_duration = int(self.current_session.get("game_duration_ms", 0))
        progress_index_ms = self.calculate_progress_index_ms(game_duration, total_lapse_duration, rounds_correct)
        mode_key = str(self.current_session.get("mode", "normal"))
        category_key = str(self.current_session.get("category", "numbers"))
        stopped_level = LEVELS[self.level_index]["level"]

        session_entry = {
            "started_at": self.current_session["started_at"],
            "ended_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "score": final_score,
            "accuracy_percent": self.calculate_accuracy(rounds_correct, rounds_played),
            "rounds_played": rounds_played,
            "rounds_correct": rounds_correct,
            "total_response_time_ms": total_response_time,
            "average_response_time_ms": avg_response_time,
            "lapse_count": lapse_count,
            "total_lapse_duration_ms": total_lapse_duration,
            "average_lapse_duration_ms": avg_lapse_duration,
            "longest_lapse_ms": longest_lapse,
            "progress_index_ms": progress_index_ms,
            "lapses": list(self.current_session["lapses"]),
            "level_history": list(self.current_session["level_history"]),
            "game_duration_ms": game_duration,
            "mode": mode_key,
            "mode_label": GAME_MODES.get(mode_key, "Normal"),
            "category": category_key,
            "category_label": GAME_CATEGORIES.get(category_key, "Grid"),
            "starting_level": int(self.current_session.get("starting_level", stopped_level)),
            "stopped_level": stopped_level,
            "stopped_level_index": self.level_index,
            "stopped_grid_size": self.grid_size,
            "highest_level_reached": int(self.current_session.get("highest_level_reached", 1)),
        }

        lifetime = player.setdefault("lifetime", {})
        self.save_mode_progress_for_player(player, category_key, mode_key)
        lifetime["rounds_played"] = int(lifetime.get("rounds_played", 0)) + rounds_played
        lifetime["rounds_correct"] = int(lifetime.get("rounds_correct", 0)) + rounds_correct
        lifetime["total_response_time_ms"] = int(lifetime.get("total_response_time_ms", 0)) + total_response_time
        lifetime["total_lapse_count"] = int(lifetime.get("total_lapse_count", 0)) + lapse_count
        lifetime["total_lapse_duration_ms"] = int(lifetime.get("total_lapse_duration_ms", 0)) + total_lapse_duration
        lifetime["total_game_duration_ms"] = int(lifetime.get("total_game_duration_ms", 0)) + game_duration
        lifetime["longest_lapse_ms"] = max(int(lifetime.get("longest_lapse_ms", 0)), longest_lapse)
        lifetime["sessions_played"] = int(lifetime.get("sessions_played", 0)) + 1
        lifetime["best_score"] = max(int(lifetime.get("best_score", 0)), final_score)
        lifetime["average_response_time_ms"] = (
            round(int(lifetime["total_response_time_ms"]) / int(lifetime["rounds_played"]))
            if int(lifetime["rounds_played"]) else 0
        )
        lifetime["average_lapse_duration_ms"] = (
            round(int(lifetime["total_lapse_duration_ms"]) / int(lifetime["total_lapse_count"]))
            if int(lifetime["total_lapse_count"]) else 0
        )
        lifetime["progress_index_ms"] = self.calculate_progress_index_ms(
            int(lifetime.get("total_game_duration_ms", 0)),
            int(lifetime.get("total_lapse_duration_ms", 0)),
            int(lifetime.get("rounds_correct", 0)),
        )

        player.setdefault("sessions", []).append(session_entry)
        player["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        players[self.active_player_key] = player
        self.player_store["players"] = players
        self.player_store["last_player_key"] = self.active_player_key
        self.active_player = player
        self.best_score = int(lifetime["best_score"])
        self.save_store()
        self.refresh_stats_display()
        self.refresh_post_game_summary()

    def open_results_with_password(self) -> None:
        password = simpledialog.askstring("Results password", "Enter password to open results:", show="*")
        if password is None:
            return
        if password != RESULTS_PASSWORD:
            messagebox.showerror("Wrong password", "Incorrect password.")
            return
        self.show_results_dashboard()

    def show_results_dashboard(self) -> None:
        players_db = self.player_store.get("players", {})
        if not players_db:
            messagebox.showinfo("Results", "No players found in the database.")
            return

        result_window = tk.Toplevel(self.root)
        result_window.title("Professional Results Dashboard")
        result_window.geometry("1200x820")
        result_window.configure(bg="#ffffff")

        top_frame = tk.Frame(result_window, bg="#ffffff")
        top_frame.pack(fill="x", padx=16, pady=12)

        tk.Label(top_frame, text="Select Player:", font=("Arial", 12, "bold"), bg="#ffffff").pack(side="left")

        player_keys = list(players_db.keys())
        player_names = [f"{players_db[k].get('name', 'Unknown')} (Age {players_db[k].get('age', '?')})" for k in player_keys]
        
        selected_player_var = tk.StringVar()
        player_selector = ttk.Combobox(top_frame, textvariable=selected_player_var, values=player_names, state="readonly", width=40)
        player_selector.pack(side="left", padx=10)

        header = tk.Frame(result_window, bg="#ffffff")
        header.pack(fill="x", padx=16, pady=(0, 12))
        
        title_label = tk.Label(header, font=("Arial", 18, "bold"), bg="#ffffff", fg="#243447")
        title_label.pack(anchor="w")
        
        stats_label = tk.Label(header, font=("Arial", 11), bg="#ffffff", fg="#4b5d73", wraplength=1150, justify="left")
        stats_label.pack(anchor="w", pady=(4, 0))

        plot_container = tk.Frame(result_window, bg="#ffffff")
        plot_container.pack(fill="both", expand=True, padx=12, pady=12)
        
        bottom = tk.Frame(result_window, bg="#ffffff")
        bottom.pack(fill="x", padx=16, pady=(0, 12))
        level_summary_label = tk.Label(bottom, font=("Arial", 10), bg="#ffffff", fg="#4b5d73", wraplength=1100, justify="left")
        level_summary_label.pack(anchor="w")

        fig = Figure(figsize=(14, 11), dpi=100)
        ax1 = fig.add_subplot(321)
        ax2 = fig.add_subplot(322)
        ax3 = fig.add_subplot(323)
        ax4 = fig.add_subplot(324)
        ax5 = fig.add_subplot(325)
        ax6 = fig.add_subplot(326)
        
        canvas = FigureCanvasTkAgg(fig, master=plot_container)
        canvas.get_tk_widget().pack(fill="both", expand=True)

        def update_dashboard(*args):
            idx = player_selector.current()
            if idx < 0: return
            p_key = player_keys[idx]
            player_data = players_db[p_key]
            
            sessions = player_data.get("sessions", [])
            
            title_label.config(text=f"Lifetime Results for {player_data.get('name', 'Unknown')} (Age {player_data.get('age', '?')})")
            
            overall_summary = self.summarize_sessions(sessions)
            
            stats_label.config(text=(
                f"Sessions Played: {overall_summary['sessions']}   |   "
                f"Total Rounds: {overall_summary['rounds']}   |   "
                f"Overall Accuracy: {overall_summary['accuracy']}%   |   "
                f"Best Score: {overall_summary['best_score']}   |   "
                f"Lifetime Avg Response: {self.format_seconds(int(overall_summary['avg_response_ms']))}   |   "
                f"Total Lapse Time: {self.format_duration_compact(int(overall_summary['total_lapse_ms']))}   |   "
                f"Progress Index: {self.format_progress_index(overall_summary['progress_index_ms'])}"
            ))

            for ax in (ax1, ax2, ax3, ax4, ax5, ax6):
                ax.clear()

            all_level_history = []
            all_lapses = []
            highest_levels_per_session = []
            
            for s in sessions:
                all_level_history.extend(s.get("level_history", []))
                all_lapses.extend(s.get("lapses", []))
                highest_levels_per_session.append(s.get("highest_level_reached", 1))
                
            rounds = list(range(1, len(all_level_history) + 1))
            sessions_played = list(range(1, len(sessions) + 1))
            response_secs = [item.get("response_time_ms", 0) / 1000 for item in all_level_history]
            levels = [item.get("level", 0) for item in all_level_history]
            
            mode_stats = {}
            for item in all_level_history:
                mode = item.get("game_type_label", item.get("mode", "Unknown"))
                # Shorten long mode names to fit
                if "Mental Reversal" in mode: mode = "Reversal"
                elif "Grid Rotation" in mode: mode = mode.replace("Grid Rotation", "Rot")
                mode_stats.setdefault(mode, {"total": 0, "correct": 0})
                mode_stats[mode]["total"] += 1
                mode_stats[mode]["correct"] += 1 if item.get("correct", False) else 0

            modes = list(mode_stats.keys())
            mode_accs = [100 * mode_stats[m]["correct"] / mode_stats[m]["total"] for m in modes]

            level_summary = {}
            for item in all_level_history:
                lvl = item.get("level", 0)
                level_summary.setdefault(lvl, {"total": 0, "correct": 0, "response": []})
                level_summary[lvl]["total"] += 1
                level_summary[lvl]["correct"] += 1 if item.get("correct", False) else 0
                level_summary[lvl]["response"].append(item.get("response_time_ms", 0) / 1000)

            summary_levels = sorted(level_summary.keys())
            summary_accuracy = [100 * level_summary[lvl]["correct"] / level_summary[lvl]["total"] for lvl in summary_levels]
            summary_avg_response = [
                sum(level_summary[lvl]["response"]) / len(level_summary[lvl]["response"])
                for lvl in summary_levels
            ]

            lapse_durations = self.get_continuous_lapse_durations(all_lapses)

            if rounds:
                ax1.plot(rounds, response_secs, marker=".", markersize=5, linestyle="-", linewidth=1, color="#2c7fb8")
                ax1.set_title("Response Time Trend (All Rounds)", fontsize=10)
                ax1.set_xlabel("Cumulative Round", fontsize=9)
                ax1.set_ylabel("Seconds", fontsize=9)
                ax1.grid(True, linestyle="--", alpha=0.4)

                ax2.plot(rounds, levels, marker=".", markersize=5, linestyle="-", linewidth=1, color="#f03b20")
                ax2.set_title("Level Progression (All Rounds)", fontsize=10)
                ax2.set_xlabel("Cumulative Round", fontsize=9)
                ax2.set_ylabel("Level", fontsize=9)
                ax2.grid(True, linestyle="--", alpha=0.4)
                
                bars3 = ax3.bar(modes, mode_accs, color="#31a354")
                ax3.set_title("Accuracy by Game Mode", fontsize=10)
                ax3.set_ylabel("Accuracy %", fontsize=9)
                ax3.set_ylim(0, 115)
                for bar in bars3:
                    yval = bar.get_height()
                    ax3.text(bar.get_x() + bar.get_width()/2.0, yval + 2, f"{int(yval)}%", ha='center', va='bottom', fontsize=9)
                ax3.tick_params(axis='x', rotation=10, labelsize=9)

                bars4 = ax4.bar(sessions_played, highest_levels_per_session, color="#756bb1")
                ax4.set_title("Peak Level Reached per Session", fontsize=10)
                ax4.set_xlabel("Session Number", fontsize=9)
                ax4.set_ylabel("Max Level", fontsize=9)
                ax4.set_xticks(sessions_played)
                
                if lapse_durations:
                    lapse_indexes = list(range(1, len(lapse_durations) + 1))
                    total_lapse_ms = sum(int(entry.get("duration_ms", 0)) for entry in all_lapses)
                    bar_width = 0.8 if len(lapse_durations) <= 40 else 0.55
                    bars5 = ax5.bar(lapse_indexes, lapse_durations, color="#e6550d", width=bar_width)
                    ax5.set_title(
                        f"Attention Lapses (Total Time: {self.format_duration_compact(total_lapse_ms)})",
                        fontsize=10,
                    )
                    ax5.set_xlabel("Lapse Event Index", fontsize=9)
                    ax5.set_ylabel("Duration (Secs)", fontsize=9)
                    ax5.set_xlim(0.5, len(lapse_durations) + 0.5)
                    max_lapse_duration = max(lapse_durations)
                    ax5.set_ylim(0, max_lapse_duration if max_lapse_duration else 1)
                    ax5.grid(True, axis='y', linestyle="--", alpha=0.4)
                else:
                    ax5.text(0.5, 0.5, "No lapses recorded\nExcellent focus!", ha="center", va="center", color="#31a354", fontsize=11, fontweight='bold')
                    ax5.set_title("Attention Lapses", fontsize=10)
                    ax5.set_xticks([])
                    ax5.set_yticks([])

                bars6 = ax6.bar(summary_levels, summary_avg_response, color="#1c9099")
                ax6.set_title("Average Response Time by Level", fontsize=10)
                ax6.set_xlabel("Level", fontsize=9)
                ax6.set_ylabel("Seconds", fontsize=9)
                ax6.set_xticks(summary_levels)
                for bar in bars6:
                    yval = bar.get_height()
                    ax6.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, f"{yval:.1f}s", ha='center', va='bottom', fontsize=9)
            else:
                for ax in (ax1, ax2, ax3, ax4, ax5, ax6):
                    ax.text(0.5, 0.5, "Insufficient Data", ha="center", va="center", color="#888888")
                    ax.set_xticks([])
                    ax.set_yticks([])

            fig.tight_layout(pad=2.0)
            canvas.draw()

            level_text = " | ".join(
                f"L{lvl}: acc {summary_accuracy[i]:.0f}%, avg {summary_avg_response[i]:.2f}s"
                for i, lvl in enumerate(summary_levels)
            )
            level_summary_label.config(text=level_text if level_text else "No per-level summary available.")

        player_selector.bind("<<ComboboxSelected>>", update_dashboard)
        
        if self.active_player_key in player_keys:
            idx = player_keys.index(self.active_player_key)
            player_selector.current(idx)
        else:
            player_selector.current(0)
            
        update_dashboard()

    def delete_current_player_data(self) -> None:
        if not self.active_player_key:
            messagebox.showwarning("No player", "No current player is selected.")
            return
        if not messagebox.askyesno("Delete player data", "Delete all saved data for the current player?"):
            return

        players = self.player_store.setdefault("players", {})
        players.pop(self.active_player_key, None)
        self.player_store["last_player_key"] = ""
        self.save_store()

        self.active_player_key = None
        self.active_player = None
        self.best_score = 0
        self.current_player_var.set("No player selected")
        self.message_text.set("Current player data deleted. Enter another player to begin.")
        self.refresh_stats_display()

    def reset_game(self) -> None:
        if self.current_idle_lapse_start_ms is not None:
            now_ms = int(time.time() * 1000)
            duration_ms = now_ms - self.current_idle_lapse_start_ms
            self.record_lapse(self.current_idle_lapse_start_ms, duration_ms, "no_input_idle")
            self.current_idle_lapse_start_ms = None

        if self.started and int(self.current_session["rounds_played"]) > 0 and not self.pending_persisted:
            if self.session_start_ms is not None:
                self.current_session["game_duration_ms"] = int(time.time() * 1000) - self.session_start_ms
            self.persist_session_data(self.score)
            self.pending_persisted = True

        self.cancel_jobs()
        self.restore_grid_from_float()
        self.stop_session_timer()
        self.started = False
        self.phase = "idle"
        self.level_index = 1  # Reset to level 2
        self.sequence = []
        self.selected = []
        self.score = 0
        self.stars = 0
        self.lives = 3
        self.session_start_ms = None
        self.stop_after_round = False

        # Reset progression
        self.consecutive_correct = 0
        self.recovery_mode = False
        self.recovery_target_level = 0

        # Reset grid
        self.grid_tier_index = 0
        self.grid_size = GRID_TIERS[0]
        self.levels_completed_in_tier = 0
        self.rebuild_grid_buttons()

        # Reset letter association
        self.letter_assignments = {}
        self.waiting_for_letter = False
        self.letter_step_index = 0

        # Reset mixed mode
        self.current_active_mode = "normal"

        self.reset_grid_rotation()
        self.timer_text.set("")
        self.message_text.set("Enter player details, choose a category and game type, then click Start Game.")
        self.post_game_summary_var.set("")
        self.current_session = self.empty_session_stats()
        self.refresh_grid_appearance()
        self.refresh_stats_display()
        self.record_app_activity()

    def cancel_jobs(self) -> None:
        self.stop_float_animation()
        if self.show_job is not None:
            try:
                self.root.after_cancel(self.show_job)
            except tk.TclError:
                pass
            self.show_job = None
        if self.next_round_job is not None:
            try:
                self.root.after_cancel(self.next_round_job)
            except tk.TclError:
                pass
            self.next_round_job = None

    def on_close(self) -> None:
        if self.current_idle_lapse_start_ms is not None:
            now_ms = int(time.time() * 1000)
            duration_ms = now_ms - self.current_idle_lapse_start_ms
            self.record_lapse(self.current_idle_lapse_start_ms, duration_ms, "no_input_idle")
            self.current_idle_lapse_start_ms = None

        if self.started and int(self.current_session["rounds_played"]) > 0 and not self.pending_persisted:
            if self.session_start_ms is not None:
                self.current_session["game_duration_ms"] = int(time.time() * 1000) - self.session_start_ms
            self.persist_session_data(self.score)

        self.stop_global_lapse_watch()
        self.stop_session_timer()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    MemoryGameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
