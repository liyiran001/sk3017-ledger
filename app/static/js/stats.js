/* 统计页：三张图表 + 预算提示，所有数据来自服务端 SQL 聚合接口 */
(function () {
  const pie = echarts.init(document.getElementById("chart-pie"));
  const bar = echarts.init(document.getElementById("chart-bar"));
  const line = echarts.init(document.getElementById("chart-line"));
  const monthPicker = document.getElementById("month-picker");

  const money = v => "¥" + Number(v).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function renderPie(rows) {
    if (!rows.length) {
      pie.clear();
      pie.setOption({ title: { text: "本月暂无支出", left: "center", top: "middle",
        textStyle: { color: "#98a2b3", fontSize: 14, fontWeight: "normal" } } });
      return;
    }
    pie.setOption({
      tooltip: { trigger: "item", formatter: p => `${p.name}<br/>${money(p.value)}（${p.percent}%）` },
      legend: { bottom: 0, type: "scroll" },
      series: [{
        type: "pie", radius: ["42%", "68%"], center: ["50%", "45%"],
        itemStyle: { borderRadius: 6, borderColor: "#fff", borderWidth: 2 },
        label: { formatter: "{b}\n{d}%" },
        data: rows
      }]
    }, true);
  }

  function renderBar(d) {
    bar.setOption({
      tooltip: { trigger: "axis", valueFormatter: money },
      legend: { bottom: 0 },
      grid: { left: 55, right: 20, top: 30, bottom: 55 },
      xAxis: { type: "category", data: d.months },
      yAxis: { type: "value", splitLine: { lineStyle: { type: "dashed" } } },
      series: [
        { name: "收入", type: "bar", data: d.income, itemStyle: { color: "#2e9e5b" }, barGap: "10%" },
        { name: "支出", type: "bar", data: d.expense, itemStyle: { color: "#e05a4f" } }
      ]
    }, true);
  }

  function renderLine(d) {
    line.setOption({
      tooltip: { trigger: "axis", valueFormatter: money },
      grid: { left: 55, right: 20, top: 30, bottom: 40 },
      xAxis: { type: "category", boundaryGap: false, data: d.days },
      yAxis: { type: "value", splitLine: { lineStyle: { type: "dashed" } } },
      series: [{
        name: "支出", type: "line", smooth: true, data: d.values,
        areaStyle: { opacity: 0.15 }, itemStyle: { color: "#2f6fed" }
      }]
    }, true);
  }

  function renderSummary(d) {
    document.getElementById("m-income").textContent = money(d.income);
    document.getElementById("m-expense").textContent = money(d.expense);
    const bal = document.getElementById("m-balance");
    bal.textContent = money(d.balance);
    bal.className = "metric-value " + (d.balance >= 0 ? "text-income" : "text-expense");

    const budgetEl = document.getElementById("m-budget");
    const banner = document.getElementById("budget-banner");
    if (d.budget && d.budget_percent !== null) {
      budgetEl.textContent = d.budget_percent + "%";
      budgetEl.className = "metric-value " + (d.budget_percent >= 100 ? "text-expense" : "");
      const over = d.budget_percent >= 100;
      const near = d.budget_percent >= 80;
      banner.classList.toggle("d-none", !near);
      banner.classList.toggle("danger", over);
      banner.innerHTML = over
        ? `⚠️ 本月支出已超预算：<b>${money(d.expense)}</b> / 预算 ${money(d.budget)}（${d.budget_percent}%）`
        : `本月已使用预算 <b>${d.budget_percent}%</b>（${money(d.expense)} / ${money(d.budget)}），接近上限了。`;
    } else {
      budgetEl.textContent = "未设置";
      budgetEl.className = "metric-value";
      banner.classList.add("d-none");
    }
  }

  function fetchJson(url) {
    return fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(r => {
        if (r.status === 401) { location.href = "/auth/login"; throw new Error("401"); }
        return r.json();
      });
  }

  function loadAll() {
    const month = monthPicker.value;
    const q = "?month=" + encodeURIComponent(month);
    fetchJson("/stats/api/summary" + q).then(r => renderSummary(r.data)).catch(() => {});
    fetchJson("/stats/api/pie" + q).then(r => renderPie(r.data)).catch(() => {});
    fetchJson("/stats/api/line" + q).then(r => renderLine(r.data)).catch(() => {});
    fetchJson("/stats/api/bar?months=6").then(r => renderBar(r.data)).catch(() => {});
  }

  monthPicker.addEventListener("change", loadAll);

  document.getElementById("btn-budget").addEventListener("click", () => {
    const month = monthPicker.value;
    fetch("/stats/api/budget?month=" + encodeURIComponent(month))
      .then(r => r.json())
      .then(res => {
        const current = res.data && res.data.amount ? res.data.amount : "";
        const input = prompt(`${month} 的月度总预算（元）：`, current);
        if (input === null || input.trim() === "") return;
        return fetch("/stats/api/budget", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ month: month, amount: input.trim() })
        }).then(r => r.json()).then(res2 => {
          if (res2.code !== 0) { alert(res2.msg || "保存失败"); return; }
          loadAll();
        });
      })
      .catch(() => alert("网络异常，请稍后重试"));
  });

  window.addEventListener("resize", () => { pie.resize(); bar.resize(); line.resize(); });
  loadAll();
})();
