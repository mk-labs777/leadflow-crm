(() => {
  const button = document.getElementById('add-item');
  const total = document.getElementById('id_items-TOTAL_FORMS');
  button.addEventListener('click', () => {
    const index = Number(total.value);
    if (index >= 20) { button.disabled = true; return; }
    const html = document.getElementById('empty-item').innerHTML.replaceAll('__prefix__', String(index));
    document.getElementById('quote-items').insertAdjacentHTML('beforeend', html);
    total.value = index + 1;
    if (index + 1 >= 20) button.disabled = true;
  });
})();
