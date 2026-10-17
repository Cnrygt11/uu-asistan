# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

Source: [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) (MIT).

---

## Proje kuralları (UÜ Asistan)

- **İletişim Türkçe.** Kod adları da Türkçe (`parcalar`, `madde_metni`); mevcut stile uy.
- **Kaynak yalnızca KAYSIS.** `data/raw/kaysis/` dışından belge eklenmez.
- **Doğrulama:** her değişiklikten sonra `python -m pytest` ve `python scripts/test_seti_dogrula.py`. `uuasistan/metin.py` veya `parcalama.py` değişirse önce `python -m uuasistan.hazirla` çalıştır ve üretilen dosyaları da commit'le. Shell ile dosya düzenlediysen sonucu çalıştırarak kontrol et.
- **Test seti (`eval/test_seti.json`):**
  - `dogrulandi: true` yalnızca kullanıcı tarafından yapılır.
  - `beklenen_cevap` değişirse `dogrulandi` false olur.
  - `beklenen_cevap` öğrenciye gidecek metindir; "Sistem/Model şunu yapmalı" gibi talimatlar `beklenen_davranis`'a yazılır.
- **Deney sonuçları** `eval-v1` etiketiyle raporlanır. 60 soruda Recall@5 farkı ~0.02'den (bir soru) küçükse gürültü kabul edilir.
- **İstenmeyen araç/script ekleme.** Faydalı olabilecek bir şey görürsen önce öner, onay gelince yap.
