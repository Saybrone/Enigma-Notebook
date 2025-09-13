import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet
import curses
import sys
import copy


def editor(stdscr, path=None):
    global fernet
    curses.curs_set(1)
    stdscr.clear()
    max_y, max_x = stdscr.getmaxyx()
    text = []
    cursor_y, cursor_x = 0, 0
    scroll_offset = 0
    undo_stack = []
    redo_stack = []
    def snapshot():
        return (copy.deepcopy(text), cursor_y, cursor_x, scroll_offset)

    def restore(state):
        nonlocal text, cursor_y, cursor_x, scroll_offset
        text, cursor_y, cursor_x, scroll_offset = copy.deepcopy(state[0]), state[1], state[2], state[3]

    try:
        if fernet is not None and path is not None:
            try:
                with open(path, "r") as fh:
                    encrypted = fh.read().encode()
                    decrypted = fernet.decrypt(encrypted).decode()
                    text = decrypted.splitlines()
            except Exception as e:
                print("Error opening file:", e)
                text = [""]
        else:
            text = [""]

        while True:
            stdscr.clear()
            for i in range(max_y - 1):
                line_index = scroll_offset + i
                if line_index >= len(text):
                    break
                stdscr.addstr(i, 0, text[line_index][:max_x-1])
            display = f"F1 Save | F2 Quit |F3 Undo | F4 Redo | Ln {cursor_y+1}, Col {cursor_x+1}"
            stdscr.addstr(max_y-1, 0, display[:max_x-1], curses.A_REVERSE)
            screen_y = cursor_y - scroll_offset
            if 0 <= screen_y < max_y-1:
                stdscr.move(screen_y, min(cursor_x, max_x-2))
            stdscr.refresh()

            key = stdscr.getch()

            if key == curses.KEY_UP:
                cursor_y = max(0, cursor_y-1)
                cursor_x = min(cursor_x, len(text[cursor_y]))
                if cursor_y < scroll_offset:
                    scroll_offset -= 1

            elif key == curses.KEY_DOWN:
                cursor_y = min(len(text)-1, cursor_y+1)
                cursor_x = min(cursor_x, len(text[cursor_y]))
                if cursor_y - scroll_offset >= max_y - 1:
                    scroll_offset += 1

            elif key == curses.KEY_LEFT:
                if cursor_x > 0:
                    cursor_x -= 1
                elif cursor_y > 0:
                    cursor_y -= 1
                    cursor_x = len(text[cursor_y])
                    if cursor_y < scroll_offset:
                        scroll_offset -= 1

            elif key == curses.KEY_RIGHT:
                if cursor_x < len(text[cursor_y]):
                    cursor_x += 1
                elif cursor_y < len(text)-1:
                    cursor_y += 1
                    cursor_x = 0
                    if cursor_y - scroll_offset >= max_y - 1:
                        scroll_offset += 1

            elif key in (10, 13):
                undo_stack.append(snapshot())
                redo_stack.clear()
                rest = text[cursor_y][cursor_x:]
                text[cursor_y] = text[cursor_y][:cursor_x]
                text.insert(cursor_y+1, rest)
                cursor_y += 1
                cursor_x = 0
                if cursor_y - scroll_offset >= max_y - 1:
                    scroll_offset += 1

            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if cursor_x > 0 or cursor_y > 0:
                    undo_stack.append(snapshot())
                    redo_stack.clear()
                if cursor_x > 0:
                    text[cursor_y] = text[cursor_y][:cursor_x-1] + text[cursor_y][cursor_x:]
                    cursor_x -= 1
                elif cursor_y > 0:
                    prev_len = len(text[cursor_y-1])
                    text[cursor_y-1] += text[cursor_y]
                    del text[cursor_y]
                    cursor_y -= 1
                    cursor_x = prev_len
                    if cursor_y < scroll_offset:
                        scroll_offset -= 1

            elif key == curses.KEY_F1:
                if path:
                    with open(path, "w") as fh:
                        writetext = "\n".join(text)
                        fh.write(fernet.encrypt(writetext.encode()).decode())
                else:
                    stdscr.addstr(max_y-1, 0, " " * (max_x-1), curses.A_REVERSE)
                    stdscr.addstr(max_y-1, 0, "Enter filename to save:", curses.A_REVERSE)
                    curses.echo()
                    fname = stdscr.getstr(max_y-1, 24).decode()
                    curses.noecho()
                    if fname:
                        path = fname
                        with open(path, "w") as fh:
                            writetext = "\n".join(text)
                            fh.write(fernet.encrypt(writetext.encode()).decode())

            elif key == curses.KEY_F2:
                if path:
                    with open(path, "w") as fh:
                        writetext = "\n".join(text)
                        fh.write(fernet.encrypt(writetext.encode()).decode())
                else:
                    stdscr.addstr(max_y-1, 0, " " * (max_x-1), curses.A_REVERSE)
                    stdscr.addstr(max_y-1, 0, "Enter filename to save:", curses.A_REVERSE)
                    curses.echo()
                    fname = stdscr.getstr(max_y-1, 24).decode()
                    curses.noecho()
                    if fname:
                        path = fname
                        with open(path, "w") as fh:
                            writetext = "\n".join(text)
                            fh.write(fernet.encrypt(writetext.encode()).decode())
                break

            elif key == curses.KEY_F3:
                if undo_stack:
                    redo_stack.append(snapshot())
                    restore(undo_stack.pop())

            elif key == curses.KEY_F4: 
                if redo_stack:
                    undo_stack.append(snapshot())
                    restore(redo_stack.pop())

            elif 32 <= key <= 126:
                undo_stack.append(snapshot())
                redo_stack.clear()
                text[cursor_y] = text[cursor_y][:cursor_x] + chr(key) + text[cursor_y][cursor_x:]
                cursor_x += 1
                if cursor_x >= max_x - 1:
                    cursor_x = 0
                    cursor_y += 1
                    text.insert(cursor_y, "")
                    if cursor_y - scroll_offset >= max_y - 1:
                        scroll_offset += 1

    except Exception as e:
        print("Editor crashed:", e)



filename = sys.argv[1] if len(sys.argv) > 1 else None

pswd = input("Enter password: ").encode()
kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b"",
    iterations=390000,
)
key = base64.urlsafe_b64encode(kdf.derive(pswd))
fernet = Fernet(key)

curses.wrapper(editor, filename)
