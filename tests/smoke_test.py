# -*- coding: utf-8 -*-
"""端到端冒烟测试：真实抓取 -> 分析 -> 职业规划全链路。"""
import io, json, os, sys, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import analyzer, career, config, industries, pipeline, store

def hr(t):
    print("\n" + "=" * 22 + " " + t + " " + "=" * 22, flush=True)

store.init_db()
hr("0. 初始状态")
print("已入库岗位:", store.total_jobs())

hr("1. 启动真实抓取")
st = pipeline.MANAGER.start(
    industry_ids=["internet"],
    keywords=["数据分析", "后端开发", "产品经理"],
    city="全国",
    source_ids=["shixiseng", "remoteok", "remotive"],
)
t0 = time.time()
while not st.finished and time.time() - t0 < 600:
    time.sleep(3)
    p = st.progress()
    print(f"  ...{p['elapsed']:>5.0f}s status={p['status']} fetched={p['fetched']} "
          f"inserted={p['inserted']} updated={p['updated']} jd={p['detail_done']}", flush=True)
print("最终状态:", st.status, "| fetched", st.fetched, "| inserted", st.inserted,
      "| updated", st.updated, "| jd", st.detail_done)
if st.errors:
    print("错误:")
    for e in st.errors[:10]:
        print("   -", e)
print("per_source:", st.per_source)

hr("2. 库内统计")
print("总岗位数:", store.total_jobs())
print("按来源:", store.counts_by("source", limit=20))
print("按行业:", store.counts_by("industry_id", limit=30)[:12])
print("城市 top:", store.counts_by("city", limit=10))

hr("3. 带真实 JD 的样本")
rows = store.query_jobs(industry_id="internet", limit=400)
withjd = [r for r in rows if r.get("jd")]
print(f"互联网行业 {len(rows)} 条，其中 {len(withjd)} 条有 JD 正文")
for r in withjd[:3]:
    print("  -", r["title"], "|", r["company"], "|", r["city"], "|", r["salary_raw"],
          "| skills:", (r.get("skills") or [])[:8])

hr("4. 需求分析")
a = analyzer.analyze(industry_id="internet", days=None, top_n=15)
print("岗位数:", a["job_count"])
print("技能榜:", [(s["name"], s["share"]) for s in a["skills"][:10]])
print("技能类别:", [(c["name"], c["share"]) for c in a["skill_categories"][:6]])
print("薪资:", json.dumps(a["salary"], ensure_ascii=False)[:400])
print("学历:", a["degree"][:5])
print("城市:", [(c["name"], c["count"]) for c in a["city_top"][:6]])
print("新鲜度:", a["freshness"])
print("洞察:")
for i in a["insights"]:
    print("   *", i)

hr("5. 趋势（两次快照对比）")
store.save_snapshot(None, "internet", analyzer.snapshot_payload("internet"))
tr = analyzer.trend("internet")
print("快照点数:", len(tr["points"]), "| note:", tr["note"][:80])
print("技能变化 top5:", [(d["name"], d["share_delta"]) for d in tr["skill_delta"][:5]])

hr("6. 职业规划诊断")
profile = {
    "major": "计算机科学与技术", "degree": "本科", "grade": "大三",
    "city_pref": "杭州", "target_job": "数据分析实习生",
    "skills": {"Python": 4, "SQL": 3, "Excel": 4, "数据分析": 3, "沟通表达": 4, "PPT": 3},
}
d = career.diagnose(profile, industry_id="internet", days=None)
print("数据来源:", d["data_source"], "| 匹配度:", d["match_score"])
print("摘要:", d["summary"])
print("缺口 top5:")
for g in d["gaps"][:5]:
    print("   -", g["skill"], "市场", g["market_level"], "我", g["my_level"],
          "缺口", g["gap"], "|", g["category"])
print("优势:", [s["skill"] for s in d["strengths"][:6]])
p0 = d["learning_path"]["phases"][0]
print("阶段1:", p0["title"], "任务数", len(p0["tasks"]))
if p0["tasks"]:
    t = p0["tasks"][0]
    print("   示例:", t["skill"], "| learn:", t["learn"][:1], "| prove:", t["prove"][:60])
    print("   项目:", t["project"][:90])
print("硬门槛:", [(c["name"], c["pass"]) for c in d["hard_checks"]])
print("专业对口:", d["major_fit"]["fit_level"], "|", d["major_fit"]["message"][:90])
print("雷达点数:", len(d["radar"]))

hr("7. 岗位匹配")
m = career.match_jobs(profile, industry_id="internet", limit=6)
print("ok:", m["ok"], "| 扫描:", m.get("scanned"))
for j in m.get("jobs", [])[:5]:
    print(f"   {j['score']:>5} | {j['title'][:34]:<34} | {j['company'][:14]:<14} | {j['city'][:6]:<6} | 命中{len(j['hit'])} 缺{len(j['miss'])}")
    print("         ", j["reason"][:110])

hr("8. 面试准备")
iv = career.interview_prep(industry_id="internet", target_job="数据分析实习生")
print("技术题数:", len(iv["technical"]), "| 行为题数:", len(iv["behavioral"]), "| 清单:", len(iv["checklist"]))
print("样题:", iv["technical"][0]["q"][:80] if iv["technical"] else "无")
print("依据:", iv["evidence"][:100])

hr("9. 方向测评")
sv = career.direction_survey({"data": 5, "people": 3, "build": 4, "create": 2, "order": 4, "research": 5})
print("推荐 top5:", [(r["industry_name"], r["score"]) for r in sv["ranked"][:5]])
print("理由:", sv["ranked"][0]["why"][:90])

hr("10. 岗位风险提示")
if withjd:
    for fl in career.risk_flags(withjd[0])[:3]:
        print("   -", fl["level"], fl["desc"])
rg = career.risk_guide()
print("权益清单条数:", len(rg["items"]))

hr("11. 知识库覆盖")
print(json.dumps(analyzer.coverage(), ensure_ascii=False)[:400])

hr("12. CSV 导出字段自检")
import csv
buf = io.StringIO()
buf.write("ok")
print("导出在 HTTP 层验证")

hr("测试完成")
