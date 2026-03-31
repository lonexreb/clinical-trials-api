"""Manim diagrams for the Clinical Trials ETL Pipeline."""

from manim import *


class ArchitectureDiagram(Scene):
    """High-level architecture: CT.gov -> ETL -> Postgres -> API -> OpenAlex."""

    def construct(self):
        # Title
        title = Text("Clinical Trials ETL Pipeline", font_size=36, weight=BOLD, color=WHITE)
        subtitle = Text("Architecture Overview", font_size=20, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.2)
        self.play(Write(title), FadeIn(subtitle, shift=UP * 0.3))
        self.wait(0.5)
        self.play(FadeOut(title), FadeOut(subtitle))

        # Nodes
        ctgov = self._box("ClinicalTrials.gov\nAPI v2", color=BLUE, x=-5, y=1.5)
        ingestion = self._box("Ingestion\nService", color=TEAL, x=-1.5, y=1.5)
        parser = self._box("Parser\n+ Normalizer", color=TEAL, x=-1.5, y=-0.5)
        postgres = self._box("PostgreSQL\n578K trials", color=GREEN, x=2, y=0.5)
        api = self._box("REST API\nFastAPI", color=ORANGE, x=5, y=1.5)
        openalex = self._box("OpenAlex", color=YELLOW, x=5, y=-1)
        cron = self._box("Daily Cron\n2 AM UTC", color=PURPLE, x=-5, y=-1)

        nodes = VGroup(ctgov, ingestion, parser, postgres, api, openalex, cron)
        self.play(LaggedStart(*[FadeIn(n, scale=0.8) for n in nodes], lag_ratio=0.15))

        # Arrows
        arrows = [
            self._arrow(ctgov, ingestion, "1000/page"),
            self._arrow(ingestion, parser, "normalize"),
            self._arrow(parser, postgres, "upsert"),
            self._arrow(postgres, api, "query"),
            self._arrow(api, openalex, "/search\n/export"),
            self._arrow(cron, ingestion, "--since\nyesterday"),
        ]

        self.play(LaggedStart(*[Create(a[0]) for a in arrows], lag_ratio=0.12))
        self.play(LaggedStart(*[FadeIn(a[1]) for a in arrows], lag_ratio=0.12))
        self.wait(2)

    def _box(self, label, color, x, y):
        rect = RoundedRectangle(
            corner_radius=0.15, width=2.4, height=1.2,
            stroke_color=color, fill_color=color, fill_opacity=0.15,
        )
        text = Text(label, font_size=14, color=WHITE)
        group = VGroup(rect, text).move_to([x, y, 0])
        return group

    def _arrow(self, start, end, label_text):
        arrow = Arrow(
            start.get_right() if start.get_center()[0] < end.get_center()[0] else start.get_bottom(),
            end.get_left() if start.get_center()[0] < end.get_center()[0] else end.get_top(),
            buff=0.15, color=GRAY_B, stroke_width=2,
        )
        label = Text(label_text, font_size=10, color=GRAY_A)
        label.next_to(arrow, UP, buff=0.08)
        return arrow, label


class DataFlowDiagram(Scene):
    """Data flow: fetch -> parse -> validate -> batch upsert -> serve."""

    def construct(self):
        title = Text("Data Ingestion Flow", font_size=32, weight=BOLD)
        self.play(Write(title))
        self.wait(0.3)
        self.play(title.animate.to_edge(UP, buff=0.4).scale(0.7))

        # Steps as a horizontal pipeline
        steps = [
            ("Fetch", "CT.gov API v2\npageSize=1000\ntoken pagination", BLUE),
            ("Parse", "Nested JSON\n-> flat schema\n+ JSONB arrays", TEAL),
            ("Validate", "Pydantic v2\n21 fields\n4 date formats", GREEN),
            ("Upsert", "ON CONFLICT\nDO UPDATE\nbatch=100", ORANGE),
            ("Serve", "REST API\nsearch + export\n+ polling", YELLOW),
        ]

        boxes = VGroup()
        for i, (name, detail, color) in enumerate(steps):
            rect = RoundedRectangle(
                corner_radius=0.12, width=2.2, height=1.8,
                stroke_color=color, fill_color=color, fill_opacity=0.12,
            )
            header = Text(name, font_size=18, weight=BOLD, color=color)
            header.next_to(rect.get_top(), DOWN, buff=0.15)
            body = Text(detail, font_size=11, color=GRAY_A, line_spacing=0.6)
            body.next_to(header, DOWN, buff=0.15)
            box = VGroup(rect, header, body)
            boxes.add(box)

        boxes.arrange(RIGHT, buff=0.35)
        boxes.next_to(title, DOWN, buff=0.6)

        self.play(LaggedStart(*[FadeIn(b, shift=UP * 0.3) for b in boxes], lag_ratio=0.2))

        # Arrows between boxes
        for i in range(len(boxes) - 1):
            arrow = Arrow(
                boxes[i].get_right(), boxes[i + 1].get_left(),
                buff=0.1, color=GRAY_B, stroke_width=2,
            )
            self.play(Create(arrow), run_time=0.3)

        # Stats bar at bottom
        stats = Text(
            "578,361 trials  |  0 errors  |  12 shards  |  95 tests  |  21 schema fields",
            font_size=14, color=GRAY_B,
        )
        stats.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(stats, shift=UP * 0.2))
        self.wait(2)


class SchemaShowcase(Scene):
    """Show the enriched schema with field categories."""

    def construct(self):
        title = Text("Enriched Trial Schema", font_size=32, weight=BOLD)
        self.play(Write(title))
        self.wait(0.3)
        self.play(title.animate.to_edge(UP, buff=0.3).scale(0.7))

        # Categories
        categories = [
            ("Core Fields", [
                "trial_id (NCT ID)", "title", "phase", "status",
                "sponsor_name", "study_type", "enrollment_number",
            ], BLUE),
            ("Clinical Data", [
                "interventions (JSONB)", "primary_outcomes (JSONB)",
                "secondary_outcomes (JSONB)", "conditions (JSONB)",
                "eligibility_criteria (TEXT)",
            ], GREEN),
            ("Knowledge Graph", [
                "mesh_terms (JSONB)", "references / DOIs (JSONB)",
                "investigators (JSONB)", "locations (JSONB)",
                "source (registry)",
            ], ORANGE),
            ("Temporal", [
                "start_date", "completion_date",
                "created_at", "updated_at",
            ], PURPLE),
        ]

        cols = VGroup()
        for cat_name, fields, color in categories:
            header = Text(cat_name, font_size=16, weight=BOLD, color=color)
            field_texts = VGroup(*[
                Text(f, font_size=11, color=GRAY_A) for f in fields
            ]).arrange(DOWN, aligned_edge=LEFT, buff=0.1)

            rect = RoundedRectangle(
                corner_radius=0.1,
                width=2.8,
                height=field_texts.height + 1.0,
                stroke_color=color, fill_color=color, fill_opacity=0.08,
            )

            header.next_to(rect.get_top(), DOWN, buff=0.15)
            field_texts.next_to(header, DOWN, buff=0.2)
            col = VGroup(rect, header, field_texts)
            cols.add(col)

        cols.arrange(RIGHT, buff=0.25)
        cols.next_to(title, DOWN, buff=0.5)
        cols.scale_to_fit_width(config.frame_width - 1.0)

        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.3) for c in cols], lag_ratio=0.2))

        # Total
        total = Text("21 fields  |  5 indexes  |  4 migrations  |  JSONB for semi-structured data", font_size=13, color=GRAY_B)
        total.to_edge(DOWN, buff=0.4)
        self.play(FadeIn(total))
        self.wait(2)


class OpenAlexWorkflow(Scene):
    """Show OpenAlex's integration workflow with the API."""

    def construct(self):
        title = Text("OpenAlex Integration", font_size=32, weight=BOLD)
        self.play(Write(title))
        self.wait(0.3)
        self.play(title.animate.to_edge(UP, buff=0.3).scale(0.7))

        # Three workflow steps
        steps = [
            ("Day 0: Backfill", "GET /trials/export?format=ndjson\n\nStreams all 578K trials\nKeyset pagination\nGzip compressed", BLUE),
            ("Daily: Poll", "GET /trials/search\n  ?updated_since=yesterday\n\nReturns only changed records\nPaginate with skip/limit", GREEN),
            ("Ad-hoc: Query", "GET /trials/search\n  ?sponsor=Pfizer\n  &phase=PHASE3\n  &status=RECRUITING\n\nConditions, MeSH, DOIs", ORANGE),
        ]

        cards = VGroup()
        for step_title, body, color in steps:
            rect = RoundedRectangle(
                corner_radius=0.15, width=3.8, height=3.2,
                stroke_color=color, fill_color=color, fill_opacity=0.1,
            )
            header = Text(step_title, font_size=16, weight=BOLD, color=color)
            header.next_to(rect.get_top(), DOWN, buff=0.2)
            code = Text(body, font_size=11, color=GRAY_A, line_spacing=0.5)
            code.next_to(header, DOWN, buff=0.25)
            card = VGroup(rect, header, code)
            cards.add(card)

        cards.arrange(RIGHT, buff=0.3)
        cards.next_to(title, DOWN, buff=0.5)

        self.play(LaggedStart(*[FadeIn(c, scale=0.9) for c in cards], lag_ratio=0.25))

        # Bottom tagline
        tag = Text(
            "No auth  |  Standard JSON  |  CORS enabled  |  578,361 trials live",
            font_size=13, color=GRAY_B,
        )
        tag.to_edge(DOWN, buff=0.4)
        self.play(FadeIn(tag))
        self.wait(2)
