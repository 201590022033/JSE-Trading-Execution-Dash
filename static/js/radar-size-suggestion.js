(() => {
  'use strict';

  const inputs = {
    risk_budget: 'Risk budget (rand)',
    notional_cap: 'Notional cap (rand, optional)'
  };

  function add(parent, tag, text) {
    const element = document.createElement(tag);
    element.textContent = text;
    parent.append(element);
    return element;
  }

  function mount(target, form, plan, evaluation, intraday) {
    if (!form) return;
    if (!document.getElementById('plan-risk_budget')) {
      const calculate = form.querySelector('button[type="submit"]');
      for (const [field, caption] of Object.entries(inputs)) {
        const label = document.createElement('label');
        label.textContent = caption;
        const input = add(label, 'input', '');
        input.id = 'plan-' + field;
        input.inputMode = 'decimal';
        calculate.before(label);
      }
    }

    const section = add(target, 'section', '');
    const suggestion = plan?.size_suggestion;
    add(section, 'h5', 'Size suggestion');
    if (suggestion) {
      add(section, 'p', 'Suggestion, based on your entered stop and budget');
      add(section, 'p', suggestion.quantity + ' ' + suggestion.quantity_unit +
        ' · R' + suggestion.risk_per_unit_zar + ' price risk per unit' +
        (suggestion.notional_cap_applied ? ' · notional cap applied' : ''));
      add(section, 'p', 'Price risk before costs: R' + suggestion.price_risk_zar);
      if (suggestion.estimated_loss_zar !== null) {
        add(section, 'p', 'Estimated costs: R' + suggestion.estimated_costs_zar);
        add(section, 'p', 'R' + suggestion.estimated_loss_zar +
          ' estimated loss if the stop fills at the stop price. A gap can be worse.');
      }
    }
    if (plan?.size_suggestion_message) {
      add(section, 'p', plan.size_suggestion_message);
    } else if (!plan) {
      add(section, 'p', 'Enter an entry price, stop price and risk budget, then calculate the plan.');
    } else if (!suggestion) {
      add(section, 'p', 'Sizing is available for long cash shares and CFDs with confirmed contract terms.');
    }

    const researchStop = evaluation?.component_plan?.stop_price;
    const direction = document.getElementById('plan-direction');
    const product = document.getElementById('plan-product');
    if (!intraday || evaluation?.timeframe_minutes !== 5 ||
        evaluation.instrument !== document.getElementById('plan-instrument').value ||
        direction.value !== 'LONG' || !['CASH_SHARE', 'CFD'].includes(product.value) ||
        !/^\d+(?:\.\d+)?$/.test(researchStop || '')) return;

    const units = document.getElementById('plan-price_unit');
    const cents = units.value === 'ZAR_CENTS';
    const [whole, fraction = ''] = researchStop.split('.');
    const fractionalCents = fraction.slice(2).replace(/0+$/, '');
    const inCents = (whole + fraction.padEnd(2, '0').slice(0, 2)).replace(/^0+(?=\d)/, '') +
      (fractionalCents ? '.' + fractionalCents : '');
    const reference = cents ? inCents + ' cents' : 'R' + researchStop;
    add(section, 'p', 'Five-minute long shadow stop reference: ' + reference);
    const useStop = add(section, 'button', 'Use shadow stop in plan');
    useStop.type = 'button';
    useStop.addEventListener('click', () => {
      const stop = document.getElementById('plan-stop_trigger');
      const editor = form.closest('details');
      if (editor) editor.open = true;
      stop.value = cents ? inCents : researchStop;
      stop.dispatchEvent(new Event('input', {bubbles: true}));
      stop.focus();
    });
  }

  window.radarSizeSuggestion = {fields: Object.keys(inputs), mount};
})();
