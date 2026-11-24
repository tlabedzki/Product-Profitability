// The value of each slider while it is dragged. The server recalculates on release (updatemode "mouseup") and writes
// the same text; this only keeps the number next to the label live.
(function () {
  function text(span, value) {
    return (span.dataset.prefix || '') + Number(value).toFixed(+span.dataset.decimals || 0) + (span.dataset.suffix || '');
  }
  function bind() {
    document.querySelectorAll('.pp-rule').forEach(function (rule) {
      var thumb = rule.querySelector('.mantine-Slider-thumb');
      var span = rule.querySelector('.pp-rule-value');
      if (!thumb || !span || thumb.dataset.ppBound) { return; }
      thumb.dataset.ppBound = '1';
      new MutationObserver(function () { span.textContent = text(span, thumb.getAttribute('aria-valuenow')); })
        .observe(thumb, {attributes: true, attributeFilter: ['aria-valuenow']});
    });
  }
  new MutationObserver(bind).observe(document.documentElement, {childList: true, subtree: true});
})();
