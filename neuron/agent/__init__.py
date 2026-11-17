"""NEURON's general agent: any goal, any domain, one loop.

  capability  - what NEURON can do: each capability declares purpose, inputs, outputs, internet need,
                permissions, resources, how its output is verified, and what must be installed
  state       - everything about a job on disk (goal, criteria, plan, evidence, knowledge, decisions),
                so any model or a new session can continue from it
  context     - the slice of that state a model needs for one step, within a size budget
  loop        - understand, investigate, plan, execute, observe, verify, revise, continue
"""
