/*
 * Karmish console — owner session only.
 *
 * The previous version defined no sendMessage() while the markup called it, so
 * the primary button was dead. Everything here is wired, and every failure mode
 * reports itself in the transcript instead of failing silently.
 *
 * No secret is read or stored here. The session cookie is httpOnly and is sent
 * by the browser; this script never touches tokens, and it never renders an
 * environment value into the DOM.
 */
(function () {
    'use strict';

    var form = document.getElementById('kForm');
    var input = document.getElementById('kInput');
    var send = document.getElementById('kSend');
    var log = document.getElementById('kLog');
    var status = document.getElementById('kStatus');
    if (!form || !input || !send || !log) return;

    var MAX = 2000;
    var busy = false;

    function setState(state, label) {
        if (!status) return;
        status.setAttribute('data-state', state);
        status.textContent = label;
    }

    function scrollToEnd() {
        log.scrollTop = log.scrollHeight;
    }

    function addMessage(role, text) {
        var li = document.createElement('li');
        li.className = 'k-msg k-msg--' + role;
        var bubble = document.createElement('div');
        bubble.className = 'k-bubble';
        // textContent, never innerHTML: a command echo must not become markup.
        bubble.textContent = text;
        li.appendChild(bubble);
        log.appendChild(li);
        scrollToEnd();
        return li;
    }

    function autoGrow() {
        input.style.height = '48px';
        input.style.height = Math.min(input.scrollHeight, 168) + 'px';
    }

    function syncEnabled() {
        send.disabled = busy || input.value.trim().length === 0;
    }

    async function submit() {
        var text = input.value.trim();
        if (!text || busy) return;

        busy = true;
        syncEnabled();
        setState('busy', 'جارٍ التنفيذ…');
        addMessage('owner', text);
        input.value = '';
        autoGrow();
        syncEnabled();

        var pending = addMessage('karmish', '…');

        try {
            var response = await fetch('/api/v1/karmish/talk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ message: text })
            });

            var body = null;
            try {
                body = await response.json();
            } catch (err) {
                body = null;
            }

            pending.remove();

            if (response.status === 401 || response.status === 403) {
                setState('error', 'انتهت الجلسة');
                addMessage('error', 'هذه الجلسة مرتبطة بمالك النظام فقط. سجّل الدخول من جديد.');
                return;
            }
            if (!response.ok) {
                setState('error', 'تعذر التنفيذ');
                addMessage('error', 'تعذر تنفيذ الأمر. التفاصيل في سجل الخادم.');
                return;
            }
            if (!body || typeof body.reply !== 'string' || body.reply.length === 0) {
                setState('error', 'رد غير مفهوم');
                addMessage('error', 'وصل رد غير متوقع من الخادم.');
                return;
            }

            setState('ok', 'تم');
            addMessage('karmish', body.reply);
        } catch (err) {
            if (pending && pending.parentNode) pending.remove();
            setState('error', 'انقطاع الاتصال');
            addMessage('error', 'تعذر الاتصال بالخادم. تحقّق من الشبكة ثم أعد المحاولة.');
        } finally {
            busy = false;
            syncEnabled();
            input.focus();
        }
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        submit();
    });

    input.addEventListener('input', function () {
        if (input.value.length > MAX) input.value = input.value.slice(0, MAX);
        autoGrow();
        syncEnabled();
    });

    input.addEventListener('keydown', function (event) {
        // Enter sends, Shift+Enter is a newline. Arabic IME composition is left
        // alone, so a composed Enter is not swallowed mid-word.
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            submit();
        }
    });

    autoGrow();
    syncEnabled();
    scrollToEnd();
})();
