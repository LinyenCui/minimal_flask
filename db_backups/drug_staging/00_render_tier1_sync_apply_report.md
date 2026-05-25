# Render Tier 1 Sync — APPLY 報告

- 時間：2026-05-25 10:39:12.367085
- backup table：customers_render_tier1_backup_20260525_103837
- drug_items inserted：152（nhi 31）
- drug_diagnosis_links inserted：27（blocked 0；--add-missing-diagnosis=True）
- customers added：20（additive；prod 既有 53 不變）
- live 表（trips/completed_trips/fixed_schedules）未被操作。
- 未對既有/ live 表 delete/truncate/drop。
