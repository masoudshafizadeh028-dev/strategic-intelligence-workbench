"""تمام selectorهای رابط بله در یک جا؛ با تغییر UI فقط اینجا را به‌روز کن."""

LOGIN_URL = "https://web.bale.ai/"
CHAT_LIST_ITEM = ".chat-list__item, [data-testid='chat-item'], li[role='listitem']"
MESSAGE_ROW = ".message, [data-testid='message'], .bubble"
MESSAGE_TEXT = ".message__text, [data-testid='message-text'], .text"
MESSAGE_INPUT = "textarea, [contenteditable='true'], input[type='text']"
SEND_BUTTON = "button[type='submit'], [data-testid='send'], .send-button"
UNREAD_BADGE = ".unread, [data-testid='unread']"
