"""Test kho Prompt tập trung: nạp YAML hợp lệ, render không sót token."""

import pytest

from prompts.loader import PromptStore, PromptStoreError

ALL_FILES = [
    "mentor_prompts.yaml",
    "scenario_prompts.yaml",
    "social_prompts.yaml",
    "trap_prompts.yaml",
    "insight_prompts.yaml",
]

# Placeholder mẫu dùng để render từng template trong test.
TEMPLATE_SAMPLES = {
    "mentor_prompts.yaml": {
        "user_prompt": {
            "context": "ct",
            "history": "h",
            "user_message": "m",
        },
    },
    "scenario_prompts.yaml": {
        "user_prompt": {
            "macro_context": "ct",
            "real_news": "n",
            "companies": "c",
            "instructions": "i",
            "article_count": 3,
        },
    },
    "social_prompts.yaml": {
        "user_prompt": {
            "persona_description": "p",
            "market_context": "ct",
            "companies": "c",
            "instructions": "i",
        },
    },
    "trap_prompts.yaml": {
        "user_prompt": {
            "user_profile": "p",
            "trades": "t",
            "exposure": "e",
            "portfolio": "pf",
            "instructions": "i",
        },
    },
    "insight_prompts.yaml": {
        "user_prompt": {
            "article": "a",
            "concepts": "c",
        },
    },
}


@pytest.fixture(scope="module")
def store() -> PromptStore:
    return PromptStore()


class TestLoad:
    @pytest.mark.parametrize("filename", ALL_FILES)
    def test_all_yaml_load_as_mapping(self, store, filename):
        data = store.load(filename)
        assert isinstance(data, dict)

    def test_invalid_filename_rejected(self, store):
        with pytest.raises(PromptStoreError):
            store.load("../secret.yaml")
        with pytest.raises(PromptStoreError):
            store.load("mentor.txt")

    def test_missing_file_raises(self, store):
        with pytest.raises(PromptStoreError):
            store.load("khong_ton_tai.yaml")

    def test_require_missing_key_raises(self, store):
        with pytest.raises(PromptStoreError):
            store.require("mentor_prompts.yaml", "templates", "khong_co")


class TestRender:
    @pytest.mark.parametrize(
        "filename,template,placeholder_map",
        [
            (filename, template_key, sample_map)
            for filename, templates in TEMPLATE_SAMPLES.items()
            for template_key, sample_map in templates.items()
        ],
    )
    def test_render_no_leftover_tokens(self, store, filename, template, placeholder_map):
        rendered = store.render_template(filename, template, **placeholder_map)
        assert isinstance(rendered, str)
        assert rendered.strip(), "Template render ra chuỗi rỗng"
        assert store.leftover_tokens(rendered) == []

    def test_unknown_token_kept_intact(self, store):
        rendered = store.render("Xin chào {{vi_that}}", vi_that="bạn")
        assert rendered == "Xin chào bạn"
        assert store.render("Giữ nguyên {{la_la}}") == "Giữ nguyên {{la_la}}"

    def test_json_braces_survive_render(self, store):
        template = '{"a": 1, "b": ["{{x}}"]}'
        assert store.render(template, x="z") == '{"a": 1, "b": ["z"]}'

    def test_render_value_recurses(self, store):
        value = {
            "title": "{{company}} ra mắt",
            "list": ["{{ticker}}", {"nested": "{{industry}}"}],
            "plain": 7,
        }
        result = store.render_value(
            value, company="Cty A", ticker="AAA", industry="Ngân hàng"
        )
        assert result == {
            "title": "Cty A ra mắt",
            "list": ["AAA", {"nested": "Ngân hàng"}],
            "plain": 7,
        }


class TestSemantics:
    def test_mentor_has_8_focus_banks(self, store):
        banks = store.require("mentor_prompts.yaml", "fallback", "question_bank")
        assert set(banks) == {
            "fomo",
            "herding",
            "anchoring",
            "loss_aversion",
            "overconfidence",
            "confirmation_bias",
            "noise_trading",
            "process",
        }
        for focus_key, bank in banks.items():
            assert bank["focus"] == focus_key
            assert 1 <= len(bank["questions"]) <= 3
            assert bank["coaching_tip"]
            assert bank["concepts"]

    def test_mentor_system_prompt_bans_advice(self, store):
        prompt = store.require("mentor_prompts.yaml", "system_prompt")
        assert "MUA/BÁN" in prompt
        assert "ĐÚNG/SAI" in prompt
        assert "TUYỆT ĐỐI" in prompt

    def test_social_has_10_personas(self, store):
        personas = store.require("social_prompts.yaml", "personas")
        assert len(personas) == 10
        for pid, persona in personas.items():
            assert persona["id"] == pid
            for key in ("name", "archetype", "tone", "sentiment_range", "deception_level"):
                assert key in persona, f"Persona {pid} thiếu {key}"

    def test_trap_definitions_present(self, store):
        traps = store.require("trap_prompts.yaml", "traps")
        assert len(traps) >= 4
        for tid, trap in traps.items():
            assert trap["id"] == tid
            assert trap["description"]
            assert trap["signals"]

    def test_scenario_fallback_has_all_categories(self, store):
        templates = store.require("scenario_prompts.yaml", "fallback", "article_templates")
        assert set(templates) == {
            "macro_domestic",
            "macro_international",
            "industry",
            "company",
            "market_report",
        }
        for category, article in templates.items():
            assert article["category"] == category
            assert article["title"]
            assert article["content"]
            assert 1 <= article["impact_score"] <= 10
