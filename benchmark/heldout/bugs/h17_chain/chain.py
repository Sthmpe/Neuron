"""A singly linked list."""


class Node:
    def __init__(self, value, next=None):
        self.value, self.next = value, next


class Chain:
    def __init__(self):
        self.head = None

    def append(self, value):
        node = Node(value)
        if self.head is None:
            self.head = node
            return
        last = self.head
        while last.next:
            last = last.next
        last.next = node

    def remove(self, value):
        """Remove the first node holding `value`. Returns True if something was removed."""
        previous, node = None, self.head
        while node:
            if node.value == value:
                if previous is None:
                    self.head = None
                else:
                    previous.next = node.next
                return True
            previous, node = node, node.next
        return False

    def to_list(self):
        out, node = [], self.head
        while node:
            out.append(node.value)
            node = node.next
        return out
