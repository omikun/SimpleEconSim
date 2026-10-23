"""Safe AST-based expression evaluator for declarative scenario conditions and metrics."""

from __future__ import annotations

import ast
import operator
from typing import Any, Dict


def _logical_and(a, b):
    return a and b


def _logical_or(a, b):
    return a or b


# Whitelist of supported AST binary and comparison operators
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: _logical_and,
    ast.Or: _logical_or,
}

UNARY_OPERATORS = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class SafeExpressionEvaluator:
    """Evaluates simple arithmetic, logical, and lookup expressions safely."""

    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def eval(self, expression: str) -> Any:
        if not expression or not expression.strip():
            return True
        tree = ast.parse(expression.strip(), mode='eval')
        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return self.context.get(node.id, 0.0)

        if isinstance(node, ast.UnaryOp):
            op = UNARY_OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op)}")
            return op(self._eval_node(node.operand))

        if isinstance(node, ast.BinOp):
            op = OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported binary operator: {type(node.op)}")
            return op(self._eval_node(node.left), self._eval_node(node.right))

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for val in node.values:
                    if not self._eval_node(val):
                        return False
                return True
            elif isinstance(node.op, ast.Or):
                for val in node.values:
                    if self._eval_node(val):
                        return True
                return False
            raise ValueError(f"Unsupported boolean operator: {type(node.op)}")

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            for op_type, comparator in zip(node.ops, node.comparators):
                op = OPERATORS.get(type(op_type))
                if op is None:
                    if isinstance(op_type, ast.In):
                        right = self._eval_node(comparator)
                        if left not in right:
                            return False
                        left = right
                        continue
                    elif isinstance(op_type, ast.NotIn):
                        right = self._eval_node(comparator)
                        if left in right:
                            return False
                        left = right
                        continue
                    raise ValueError(f"Unsupported comparison operator: {type(op_type)}")
                right = self._eval_node(comparator)
                if not op(left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.Attribute):
            obj = self._eval_node(node.value)
            attr = node.attr
            if isinstance(obj, dict):
                return obj.get(attr)
            return getattr(obj, attr, None)

        if isinstance(node, ast.Subscript):
            val = self._eval_node(node.value)
            slice_val = self._eval_node(node.slice)
            try:
                return val[slice_val]
            except Exception:
                return None

        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._eval_node(elt) for elt in node.elts]

        if isinstance(node, ast.Call):
            args = [self._eval_node(arg) for arg in node.args]
            if isinstance(node.func, ast.Name):
                allowed_funcs = {'min': min, 'max': max, 'round': round, 'abs': abs, 'int': int, 'float': float, 'len': len}
                func = allowed_funcs.get(node.func.id)
                if func is not None:
                    return func(*args)
            elif isinstance(node.func, ast.Attribute):
                obj = self._eval_node(node.func.value)
                method_name = node.func.attr
                if method_name == 'get' and isinstance(obj, dict):
                    return obj.get(*args)

            raise ValueError(f"Unsupported function call in expression: {ast.dump(node.func)}")

        raise ValueError(f"Unsupported expression syntax: {type(node).__name__}")


def evaluate_condition(condition: str | None, context: Dict[str, Any]) -> bool:
    """Evaluate a boolean condition string within context. Returns True if empty."""
    if not condition or not condition.strip():
        return True
    try:
        evaluator = SafeExpressionEvaluator(context)
        return bool(evaluator.eval(condition))
    except Exception as err:
        # In case of syntax error or missing variable, evaluate to False
        return False


def evaluate_metric(expr: str, context: Dict[str, Any], default: Any = 0.0) -> Any:
    """Evaluate a numeric/value expression within context."""
    if not expr or not expr.strip():
        return default
    try:
        evaluator = SafeExpressionEvaluator(context)
        res = evaluator.eval(expr)
        return res if res is not None else default
    except Exception:
        return default
