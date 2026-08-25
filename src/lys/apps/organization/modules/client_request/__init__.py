"""
Client request module: what a client asks for, and what became of it.

A request is something a client raises through the product — a quote, a support contact,
an enquiry on a given subject — that a human or an automation has to act on. This module
owns the record and its lifecycle; what a request *means*, and what happens when one
arrives, belong to the application that declares its type.

The record exists so the demand survives whatever is supposed to handle it. An automation
that never receives a request, or fails on it, must not make the request disappear: the
row is written before any side effect is attempted, and its status says what became of it.
"""
