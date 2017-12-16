# vim: ft=python fileencoding=utf-8 sw=4 et sts=4
"""Command storage, initialization decorators and execution.

Module Attributes:
    _registry: Dictionary to store commands in.
"""

import argparse
import shlex

from PyQt5.QtCore import pyqtSignal, QObject

from vimiv.utils import objreg


registry = {}


class Signals(QObject):
    """Class to store the qt signals for others to connect to."""

    exited = pyqtSignal(int, str)


signals = Signals()


class ArgumentError(Exception):
    """Raised if a command was called with wrong arguments."""


class CommandError(Exception):
    """Raised if a command failed to run correctly."""


class CommandWarning(Exception):
    """Raised if a command wants to show the user a warning."""


def run(text):
    """Run a command given as string.

    Text is of the form:
        command [positional_arg] [--optional_arg=value].

    Args:
        text: The string to run.
    """
    if not text:
        return
    split = shlex.split(text)
    cmdname = split[0]
    args = split[1:]
    if cmdname not in registry:
        signals.exited.emit(1, "%s: unknown command" % (cmdname))
    else:
        cmd = registry[cmdname]
        try:
            cmd(args)
            signals.exited.emit(0, "")
        except (CommandError, ArgumentError) as e:
            message = "%s: %s" % (cmdname, str(e))
            signals.exited.emit(1, message)
        except CommandWarning as w:
            signals.exited.emit(2, str(w))


class Args(argparse.ArgumentParser):
    """Store and parse command arguments using argparse."""

    def __init__(self, cmdname, description=""):
        """Create the argparse.ArgumentParser.

        Args:
            cmdname: Name of the command for which the arguments are stored.
            description: Description of the command for error messages.
        """
        super().__init__(prog=cmdname, description=description)

    def error(self, message):
        """Override error to raise an exception instead of calling sys.exit."""
        if message.startswith("argument"):  # Remove argument argname:
            message = " ".join(message.split(":")[1:])
        message = message.strip()
        message = " ".join(message.split())  # Remove multiple whitespace
        message = message.capitalize()
        raise ArgumentError(message)


class Command():
    """Skeleton for a command.

    Attributes:
        args: Args class to store and parse command arguments.
        func: Corresponding executable to call.
        mode: Mode in which the command can be executed.
        name: Name of the command as string.

        _instance: Object to be passed to func as self argument if any.
    """

    def __init__(self, name, func, instance=None, mode="global"):
        self.name = name
        self.func = func
        self._instance = instance
        self.mode = mode
        self.args = Args(name)

    def __call__(self, args):
        """Parse arguments and call func."""
        parsed_args = self.args.parse_args(args)
        kwargs = vars(parsed_args)
        if self._instance:
            obj = objreg.get(self._instance)
            self.func(obj, **kwargs)
        else:
            self.func(**kwargs)


class argument:  # pylint: disable=invalid-name
    """Decorator to update command a command argument.

    As a class with "wrong" name it is cleaner to implement.

    Attributes:
        _argname: Name of the argument.
        _kwargs: kwargs to be passed to parser.parse_args.
    """

    def __init__(self, argname, optional=False, **kwargs):
        self._argname = "--%s" % (argname) if optional else argname
        self._kwargs = kwargs

    def __call__(self, func):
        cmd = self._get_command(func)
        cmd.args.add_argument(self._argname, **self._kwargs)
        return func

    def _get_command(self, func):
        """Receive corresponding command from registry."""
        funcname = func.__name__.lower().replace("_", "-")
        if funcname not in registry:  # coverage: ignore
            raise ValueError("@commands.argument got called before (below) "
                             "@commands.register for %s" % (funcname))
        cmd = registry[funcname]
        return cmd


class register:  # pylint: disable=invalid-name
    """Decorator to register a new command.

    As a class with "wrong" name it is cleaner to implement.

    Attributes:
        _instance: The object from the object registry to be used as "self".
        _mode: Mode in which the command can be executed.
    """

    def __init__(self, instance=None, mode="global"):
        self._instance = instance
        self._mode = mode

    def __call__(self, func):
        name = func.__name__.lower().replace("_", "-")
        cmd = Command(name, func, instance=self._instance, mode=self._mode)
        registry[name] = cmd
        return func