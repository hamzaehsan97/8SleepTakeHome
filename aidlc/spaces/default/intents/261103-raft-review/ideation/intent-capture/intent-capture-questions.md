# Intent Capture Questions

## Sources

- [desc] Initial description: "Review the project architecture, then review the design and code. Judge it against this take-home: build a toy consensus algorithm of our choice from scratch (no consensus or replication library), replicate state across a small cluster, and write tests that exercise the failure modes that matter. It is open ended and need not be finished; polish, reasoning, testability (even of a broken implementation) and a README note on how AI tools were used matter more than completeness."
- [scope] Workflow-selected scope: `poc`.

## Q1. [Product] What should this review hand back to you?

You asked for a review of the architecture, then the design and code. This decides whether the later build step changes any code or only reports.

- A. A written review only: findings ranked by severity, no changes to the code
- B. A written review plus fixes for the clear defects it finds
- C. A written review plus fixes, and a draft of the README note on how AI tools were used
- D. Not yet defined
- X. Other (please specify)

[Answer]: B

## Q2. [Product] Who reads the review, and what decision does it feed?

This sets the tone and depth of the review and what counts as a finding worth reporting.

- A. You, to polish the submission before sending it
- B. You, to prepare for walking the interview panel through your choices
- C. Both: polish first, then panel preparation
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Q3. [Product] Which parts of the take-home should the review weigh most?

The brief values polish, reasoning, testability (even of a broken implementation) and the README note on AI tools over completeness. Pick the emphasis, or select all that apply.

- A. Correctness of the Raft logic against the paper (elections, log replication, safety)
- B. Whether the tests exercise the failure modes that matter (partitions, crashes, message loss and reordering)
- C. Design clarity and how well the choices and trade-offs are explained
- D. The README, including the note on how AI tools were used and verified
- X. Other (please specify)

(select all that apply)

[Answer]: A, B, C, D

## Q4. [Product] What should this first version of the review leave out?

This bounds the work so the review stays small and finishes.

- A. Nothing is excluded: cover the architecture, design, code, tests and README
- B. Leave out performance and scaling; they are not part of the brief
- C. Leave out the mutation-checking tool and the example scripts; review only the Raft package, simulator and tests
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
