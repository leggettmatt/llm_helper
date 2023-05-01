import click

def click_text(s, color=None, bold=False, background=None):
    if color:
        s = click.style(s, fg=color)
    if bold:
        s = click.style(s, bold=True)
    if background:
        s = click.style(s, bg=background)
    return s

def separator(color=None):
    click.echo(click_text("--------------------------------------------------", color))