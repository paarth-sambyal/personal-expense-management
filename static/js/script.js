document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => {
    const row = JSON.parse(button.dataset.edit);
    const form = document.querySelector('#editForm');
    const kind = row.income_id ? 'income' : 'expenses';
    const id = row.income_id || row.expense_id;
    form.action = `/${kind}/${id}/edit`;
    Object.entries({source: row.source, amount: row.amount, date: row.income_date || row.expense_date,
      description: row.description, category_id: row.category_id}).forEach(([name, value]) => {
      const input = form.elements.namedItem(name);
      if (input && value !== null && value !== undefined) input.value = value;
    });
  }));
  document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));
  document.querySelector('.menu-toggle')?.addEventListener('click', () => document.body.classList.toggle('sidebar-open'));

  const palette = ['#55b894','#f3a77d','#7286d8','#e4c15b','#d27e9a','#70b6cd','#9c83c8','#93bd72'];
  const baseOptions = {responsive: true, maintainAspectRatio: false, plugins: {legend: {display: false}},
    scales: {x: {grid: {display: false}, ticks: {color: '#89949e'}}, y: {grid: {color: '#eef0f1'}, ticks: {color: '#89949e'}}}};
  const monthly = window.chartData?.monthly || window.reportData?.monthly;
  const monthlyCanvas = document.getElementById('monthlyChart') || document.getElementById('reportMonthly');
  if (monthlyCanvas && monthly?.length) new Chart(monthlyCanvas, {type: 'bar', data: {labels: monthly.map(x => x.month_label || x.month), datasets: [
    {label: 'Income', data: monthly.map(x => Number(x.income)), backgroundColor: '#70c7a4', borderRadius: 5},
    {label: 'Expenses', data: monthly.map(x => Number(x.expenses)), backgroundColor: '#f2a58f', borderRadius: 5}]}, options: {...baseOptions, plugins: {legend: {display: true, position: 'top', align: 'end', labels: {usePointStyle: true, boxWidth: 7, color: '#66717d'}}}}});
  const cats = window.chartData?.categories || window.reportData?.categories;
  const catCanvas = document.getElementById('categoryChart') || document.getElementById('reportCategories');
  if (catCanvas && cats?.length) new Chart(catCanvas, {type: 'doughnut', data: {labels: cats.map(x => x.category_name), datasets: [{data: cats.map(x => Number(x.total)), backgroundColor: palette, borderWidth: 3, borderColor: '#fff'}]}, options: {responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: {legend: {display: false}}}});
});
