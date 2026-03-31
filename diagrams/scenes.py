"""Manim diagrams for the Clinical Trials ETL Pipeline.

Render: manim -qk -s diagrams/scenes.py <SceneName>
(-qk = 4K, -s = save last frame only)
"""

from manim import *

# Consistent palette
C_BLUE = "#4A90D9"
C_TEAL = "#50B5A9"
C_GREEN = "#5CB85C"
C_ORANGE = "#E8913A"
C_YELLOW = "#F5D76E"
C_PURPLE = "#9B59B6"
C_RED = "#E74C3C"
C_BG = "#0D1117"  # GitHub dark background


class ArchitectureDiagram(Scene):
    """CT.gov -> ETL -> Postgres -> API -> OpenAlex"""

    def construct(self):
        self.camera.background_color = C_BG

        title = Text("Architecture", font_size=48, weight=BOLD, color=WHITE)
        title.to_edge(UP, buff=0.6)
        self.add(title)

        # Main pipeline: left to right
        ctgov = self._node("ClinicalTrials.gov\nAPI v2", C_BLUE, width=3.5)
        ingest = self._node("Ingestion\nEngine", C_TEAL, width=3)
        postgres = self._node("PostgreSQL\n578,361 trials", C_GREEN, width=3.5)
        api = self._node("FastAPI\nREST API", C_ORANGE, width=3)
        openalex = self._node("OpenAlex", C_YELLOW, width=3)

        main_row = VGroup(ctgov, ingest, postgres, api, openalex)
        main_row.arrange(RIGHT, buff=0.6)
        main_row.next_to(title, DOWN, buff=1.0)

        # Supporting nodes below
        cron = self._node("Daily Cron\n2 AM UTC", C_PURPLE, width=2.8)
        parser = self._node("Parser\nNormalizer", C_TEAL, width=2.8)

        cron.next_to(ingest, DOWN, buff=1.2)
        cron.shift(LEFT * 1.8)
        parser.next_to(ingest, DOWN, buff=1.2)
        parser.shift(RIGHT * 1.8)

        all_nodes = VGroup(ctgov, ingest, postgres, api, openalex, cron, parser)
        all_nodes.scale_to_fit_width(config.frame_width - 1.5)
        self.add(all_nodes)

        # Arrows with labels
        self._connect(ctgov, ingest, "pageToken\npagination", UP)
        self._connect(ingest, postgres, "batch\nupsert", UP)
        self._connect(postgres, api, "async\nquery", UP)
        self._connect(api, openalex, "/search\n/export", UP)
        self._connect(cron, ingest, "--since\nyesterday", RIGHT)
        self._connect(ingest, parser, "normalize", RIGHT)
        self._connect(parser, postgres, "JSONB\narrays", RIGHT)

    def _node(self, label, color, width=3):
        rect = RoundedRectangle(
            corner_radius=0.2, width=width, height=1.4,
            stroke_color=color, stroke_width=3,
            fill_color=color, fill_opacity=0.15,
        )
        text = Text(label, font_size=22, color=WHITE, line_spacing=0.7)
        return VGroup(rect, text)

    def _connect(self, start, end, label_text, label_dir):
        s = start.get_center()
        e = end.get_center()
        if abs(s[0] - e[0]) > abs(s[1] - e[1]):
            arrow = Arrow(start.get_right(), end.get_left(), buff=0.15, color=GRAY_B, stroke_width=2.5)
        else:
            if s[1] > e[1]:
                arrow = Arrow(start.get_bottom(), end.get_top(), buff=0.15, color=GRAY_B, stroke_width=2.5)
            else:
                arrow = Arrow(start.get_top(), end.get_bottom(), buff=0.15, color=GRAY_B, stroke_width=2.5)
        label = Text(label_text, font_size=14, color=GRAY_A, line_spacing=0.5)
        label.next_to(arrow, label_dir, buff=0.1)
        self.add(arrow, label)


class DataFlowDiagram(Scene):
    """Fetch -> Parse -> Validate -> Upsert -> Serve"""

    def construct(self):
        self.camera.background_color = C_BG

        title = Text("Data Ingestion Pipeline", font_size=48, weight=BOLD, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.add(title)

        steps = [
            ("1. Fetch", "CT.gov API v2\npageSize = 1000\nToken pagination", C_BLUE),
            ("2. Parse", "Nested JSON\n21 schema fields\n4 date formats", C_TEAL),
            ("3. Validate", "Pydantic v2\nType checking\nNull handling", C_GREEN),
            ("4. Upsert", "ON CONFLICT\nDO UPDATE\nBatch = 100", C_ORANGE),
            ("5. Serve", "REST API\nSearch + Export\nDaily polling", C_YELLOW),
        ]

        boxes = VGroup()
        for name, detail, color in steps:
            rect = RoundedRectangle(
                corner_radius=0.15, width=2.5, height=3.0,
                stroke_color=color, stroke_width=3,
                fill_color=color, fill_opacity=0.12,
            )
            header = Text(name, font_size=24, weight=BOLD, color=color)
            body = Text(detail, font_size=16, color=GRAY_A, line_spacing=0.7)
            header.next_to(rect.get_top(), DOWN, buff=0.25)
            body.next_to(header, DOWN, buff=0.25)
            boxes.add(VGroup(rect, header, body))

        boxes.arrange(RIGHT, buff=0.4)
        boxes.next_to(title, DOWN, buff=0.7)
        boxes.scale_to_fit_width(config.frame_width - 1.2)
        self.add(boxes)

        # Arrows
        for i in range(len(boxes) - 1):
            arrow = Arrow(
                boxes[i].get_right(), boxes[i + 1].get_left(),
                buff=0.1, color=GRAY_B, stroke_width=2.5,
            )
            self.add(arrow)

        # Stats bar
        stats = Text(
            "578,361 trials   |   0 errors   |   12 shards   |   95 tests   |   21 fields",
            font_size=20, color=GRAY_B,
        )
        stats.to_edge(DOWN, buff=0.6)
        self.add(stats)


class SchemaShowcase(Scene):
    """Enriched schema with 4 categories."""

    def construct(self):
        self.camera.background_color = C_BG

        title = Text("Enriched Trial Schema", font_size=48, weight=BOLD, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.add(title)

        categories = [
            ("Core", [
                "trial_id  (NCT ID, indexed)",
                "title",
                "phase  (indexed)",
                "status  (indexed)",
                "sponsor_name  (indexed)",
                "study_type",
                "enrollment_number",
            ], C_BLUE),
            ("Clinical Data", [
                "interventions  (JSONB)",
                "primary_outcomes  (JSONB)",
                "secondary_outcomes  (JSONB)",
                "conditions  (JSONB)",
                "eligibility_criteria  (TEXT)",
            ], C_GREEN),
            ("Knowledge Graph", [
                "mesh_terms  (JSONB)",
                "references / DOIs  (JSONB)",
                "investigators  (JSONB)",
                "locations  (JSONB)",
                "source  (registry)",
            ], C_ORANGE),
            ("Temporal", [
                "start_date",
                "completion_date",
                "created_at",
                "updated_at  (indexed)",
            ], C_PURPLE),
        ]

        cols = VGroup()
        for cat_name, fields, color in categories:
            header = Text(cat_name, font_size=24, weight=BOLD, color=color)
            field_lines = VGroup(*[
                Text(f, font_size=15, color=GRAY_A) for f in fields
            ]).arrange(DOWN, aligned_edge=LEFT, buff=0.12)

            content = VGroup(header, field_lines).arrange(DOWN, buff=0.25, aligned_edge=LEFT)

            rect = RoundedRectangle(
                corner_radius=0.15,
                width=content.width + 0.6,
                height=content.height + 0.6,
                stroke_color=color, stroke_width=3,
                fill_color=color, fill_opacity=0.08,
            )
            content.move_to(rect)
            cols.add(VGroup(rect, content))

        cols.arrange(RIGHT, buff=0.3, aligned_edge=UP)
        cols.next_to(title, DOWN, buff=0.6)
        cols.scale_to_fit_width(config.frame_width - 1.0)
        self.add(cols)

        footer = Text(
            "21 fields   |   5 indexes   |   4 migrations   |   JSONB for semi-structured data",
            font_size=18, color=GRAY_B,
        )
        footer.to_edge(DOWN, buff=0.5)
        self.add(footer)


class OpenAlexWorkflow(Scene):
    """3-step OpenAlex integration workflow."""

    def construct(self):
        self.camera.background_color = C_BG

        title = Text("OpenAlex Integration Workflow", font_size=48, weight=BOLD, color=WHITE)
        title.to_edge(UP, buff=0.5)
        self.add(title)

        cards_data = [
            (
                "Day 0: Backfill",
                "GET /trials/export\n    ?format=ndjson",
                "Streams all 578K trials\nKeyset pagination (O(1)/batch)\nAuto gzip compression",
                C_BLUE,
            ),
            (
                "Daily: Poll for Changes",
                "GET /trials/search\n    ?updated_since=yesterday",
                "Returns only changed records\nPaginate with skip/limit\nTypically < 1K per day",
                C_GREEN,
            ),
            (
                "Ad-hoc: Filtered Query",
                "GET /trials/search\n    ?sponsor=Pfizer\n    &phase=PHASE3\n    &status=RECRUITING",
                "Conditions, MeSH terms, DOIs\nInvestigators, eligibility\nSort by any column",
                C_ORANGE,
            ),
        ]

        cards = VGroup()
        for card_title, endpoint, description, color in cards_data:
            rect = RoundedRectangle(
                corner_radius=0.2, width=4.5, height=4.5,
                stroke_color=color, stroke_width=3,
                fill_color=color, fill_opacity=0.1,
            )

            h = Text(card_title, font_size=24, weight=BOLD, color=color)
            h.next_to(rect.get_top(), DOWN, buff=0.3)

            ep = Text(endpoint, font_size=17, color=WHITE, line_spacing=0.6)
            ep.next_to(h, DOWN, buff=0.35)

            line = Line(LEFT * 1.5, RIGHT * 1.5, color=color, stroke_width=1.5)
            line.next_to(ep, DOWN, buff=0.25)

            desc = Text(description, font_size=15, color=GRAY_A, line_spacing=0.65)
            desc.next_to(line, DOWN, buff=0.25)

            cards.add(VGroup(rect, h, ep, line, desc))

        cards.arrange(RIGHT, buff=0.4)
        cards.next_to(title, DOWN, buff=0.7)
        cards.scale_to_fit_width(config.frame_width - 1.0)
        self.add(cards)

        footer = Text(
            "No auth   |   Standard JSON   |   CORS enabled   |   578,361 trials live",
            font_size=20, color=GRAY_B,
        )
        footer.to_edge(DOWN, buff=0.5)
        self.add(footer)
