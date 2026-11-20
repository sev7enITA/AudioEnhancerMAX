(() => {
    const gap = 8;
    const margin = 12;
    let active;
    let openTimer;
    let closeTimer;

    function dismiss() {
        clearTimeout(openTimer);
        clearTimeout(closeTimer);
        if (active) {
            active.tip.hidden = true;
            active.overTip = false;
        }
        active = null;
    }

    function position(entry) {
        const {trigger, tip} = entry;
        const anchor = trigger.getBoundingClientRect();
        if (trigger.disabled || !anchor.height || anchor.bottom <= 0 || anchor.top >= innerHeight ||
            anchor.right <= 0 || anchor.left >= innerWidth) return false;
        const {width, height} = tip.getBoundingClientRect();
        const fitsBeside = trigger.closest('#sidebar') && anchor.right + gap + width <= innerWidth - margin;
        const left = fitsBeside ? anchor.right + gap : anchor.left + (anchor.width - width) / 2;
        const above = anchor.top - gap - height;
        const below = anchor.bottom + gap;
        const actions = trigger.closest('.studio-open-actions')?.getBoundingClientRect();
        const firstActionRow = actions && anchor.bottom <= actions.top + actions.height / 2;
        const opensAbove = (firstActionRow && above >= margin) || below + height > innerHeight - margin;
        const top = fitsBeside ? anchor.top + (anchor.height - height) / 2 : (opensAbove ? above : below);
        tip.style.left = Math.max(margin, Math.min(left, innerWidth - width - margin)) + 'px';
        tip.style.top = Math.max(margin, Math.min(top, innerHeight - height - margin)) + 'px';
        return true;
    }

    function show(entry) {
        dismiss();
        active = entry;
        entry.tip.style.visibility = 'hidden';
        entry.tip.hidden = false;
        if (!position(entry)) dismiss();
        entry.tip.style.removeProperty('visibility');
    }

    function leave(entry) {
        clearTimeout(openTimer);
        clearTimeout(closeTimer);
        if (active !== entry) return;
        closeTimer = setTimeout(() => {
            if (active === entry && !entry.hovered && !entry.overTip && document.activeElement !== entry.trigger) {
                dismiss();
            }
        }, 160);
    }

    const tips = document.createDocumentFragment();
    document.querySelectorAll('[data-tip]').forEach((trigger, index) => {
        const tip = document.createElement('span');
        tip.id = 'context-tip-' + (index + 1);
        tip.className = 'context-tip';
        tip.setAttribute('role', 'tooltip');
        tip.textContent = trigger.dataset.tip;
        tip.hidden = true;
        const description = trigger.getAttribute('aria-describedby');
        trigger.setAttribute('aria-describedby', [description, tip.id].filter(Boolean).join(' '));
        tips.append(tip);
        const entry = {trigger, tip, hovered: false, overTip: false};

        trigger.addEventListener('pointerenter', event => {
            if (event.pointerType !== 'mouse') return;
            entry.hovered = true;
            clearTimeout(closeTimer);
            clearTimeout(openTimer);
            if (active !== entry) openTimer = setTimeout(() => show(entry), 280);
        });
        trigger.addEventListener('pointerleave', () => {
            entry.hovered = false;
            leave(entry);
        });
        tip.addEventListener('pointerenter', () => {
            entry.overTip = true;
            clearTimeout(closeTimer);
        });
        tip.addEventListener('pointerleave', () => {
            entry.overTip = false;
            leave(entry);
        });
        trigger.addEventListener('focus', () => show(entry));
        trigger.addEventListener('blur', () => {
            if (active === entry && !entry.hovered && !entry.overTip) dismiss();
            else leave(entry);
        });
        trigger.addEventListener('click', dismiss);
    });
    document.body.append(tips);

    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        if (active) {
            event.preventDefault();
            event.stopPropagation();
        }
        dismiss();
    }, true);
    document.addEventListener('aem:panel', dismiss);
    function reposition() {
        if (active && !position(active)) dismiss();
    }
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, {capture: true, passive: true});
})();
