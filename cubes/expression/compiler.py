# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function

from .grammar import ExpressionParser, ExpressionSemantics

__all__ = [
        "ExpressionCompiler",
    ]


import json

class ASTNode(object):
    pass

class Atom(ASTNode):
    pass

class FunctionCall(Atom):
    def __init__(self, reference, args):
        self.reference = reference
        self.args = args

    def __str__(self):
        return "%s(%s)" % (self.reference, ", ".join(str(a) for a in self.args))

class VariableReference(Atom):
    def __init__(self, reference):
        self.reference = reference

    def __str__(self):
        return ".".join(self.reference)

    def __repr__(self):
        return self.__str__()

class Literal(Atom):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return "%s" % str(self.value)

class UnaryOperator(ASTNode):
    def __init__(self, operator, operand):
        self.operator = operator
        self.operand = operand

    def __str__(self):
        return "({} {})".format(str(self.operator), str(self.operand))

    def __repr__(self):
        return self.__str__()

class BinaryOperator(ASTNode):
    def __init__(self, operator, left, right):
        self.operator = operator
        self.left = left
        self.right = right

    def __str__(self):
        return "({o.left} {o.operator} {o.right})".format(o=self)

    def __repr__(self):
        return self.__str__()

class _ExpressionSemantics(object):
    def __init__(self, compiler, context):
        self.compiler = compiler
        self.context = context

    def NUMBER(self, ast):
        try:
            value = int(ast)
        except ValueError:
            value = float(ast)

        return self.compiler.compile_literal(self.context, value)

    def STRING(self, ast):
        return self.compiler.compile_literal(self.context, str(ast))

    def _default(self, ast, *args, **kwargs):
        if not args:
            return ast

        # TODO: this will not work with custom compilations
        if isinstance(ast, ASTNode):
            return ast

        if not ast[1]:
            return ast[0]

        if args[0] == "binary":
            # AST: [left, [operator, right, operator, right, ...]]
            left = ast[0]
            op = ast[1][0]

            ops = ast[1][0::2]
            rights = ast[1][1::2]

            for op, right in zip(ops, rights):
                left = self.compiler.compile_operator(self.context, op,
                                                      left, right)

            return left

        elif args[0] == "unary":
            # AST: [operator, right]
            op = ast[0]
            operand = ast[1]
            return self.compiler.compile_unary(self.context, op, operand)
        else:
            raise Exception("Unknown args %s" % args)

    def atom(self, ast):
        if ast.value is not None:
            return ast["value"]
        elif ast.ref is not None:
            if ast.get("args"):
                return self.compiler.compile_function(self.context, ast.ref,
                                                      ast.args)
            else:
                return ast.ref
        elif ast.expr is not None:
            return ast.expr
        else:
            raise Exception("Unhandled AST: %s" % ast)

    def reference(self, ast):
        return VariableReference(ast)


class ExpressionCompiler(object):
    def __init__(self, context=None):
        """Creates an expression compiler with a `context` object. The context
        object is a custom object that subclasses might use during the
        compilation process for example to get variables by name, function
        objects. Context can be also used store information while compiling
        multiple expressions such as list of used attributes for analyzing
        requirements for query construction."""
        self.context = context

    def compile(self, text, context=None):
        """Compiles the `text` expression, returns a finalized object. """

        if context is None:
            context = self.context

        parser = ExpressionParser()

        ast = parser.parse(text,
                rule_name="start",
                comments_re="#.*",
                ignorecase=False,
                semantics=_ExpressionSemantics(self, context))

        return ast

    def compile_literal(self, context, literal):
        """Compile a literal object such as number or a string. Default
        implementation returns `Literal` object with attribute `value`."""
        return Literal(literal)

    def compile_variable(self, context, reference):
        """Compile variable `reference`. Default implementation returns
        `VariableReference` object."""
        return VariableReference(reference)

    def compile_operator(self, context, operator, left, right):
        """Compile `operator` with operands `left` and `right`. Default
        implementation returns `BinaryOperator` object with attributes
        `operator`, `left` and `right`."""
        return BinaryOperator(operator, left, right)

    def compile_unary(self, context, operator, operand):
        """Called when an unary `operator` is encountered. Default
        implementation returns `UnaryOperator` object with attributes
        `operator` and `operand`"""
        return UnaryOperator(operator, operand)

    def compile_function(self, conext, function, args):
        """Called when a function call is encountered in the expression.
        `function` is a `VariableReference` object (you can use
        `str(function)` to get the full function name reference as string),
        `args` is a list of function arguments.
        """
        return FunctionCall(function, args)

    def finalize(self, context, obj):
        """Return final object as a result of expression compilation. By
        default returns the object returned by the last executed compilation
        method.

        Subclasses can override this method if they want to wrap the result
        object in another object or to finalize collected statement analysis."""
        return obj