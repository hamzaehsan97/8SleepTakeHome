# Requirements Analysis Questions

The scan found no clear Raft safety defect. It did find fixable gaps in the tests, the mutation tool, the packaging and the docs (see `aidlc/spaces/default/codekb/8sleep/code-quality-assessment.md`). These questions set which of those the build step may change.

## Q1. [Product] Which of the candidate fixes should be made?

The review will report all findings. This sets which ones are also fixed in the code, tests and docs. Select all that apply.

- A. Mutation tool: add an unmutated baseline run and stop counting syntax, import, collection and timeout errors as "caught" (tools/mutation_check.py)
- B. Tests: add negative tests that prove the invariant checker rejects a violation, and add tests for storage
- C. Packaging: declare pytest in pyproject.toml, and add a mypy config or drop the mypy claim from the README
- D. Docs: make the README and docs/design-decisions.md agree, and list docs/ in the README layout
- E. Linearizability test: guard it against a late-committing abandoned retry, or reword its claim that retries are harmless
- X. Other (please specify)

(select all that apply)

[Answer]: A, B, C, D, E

## Q2. [Product] How should the README's statements about who decided what be handled?

The README says you decided the logical-time network and which extensions to add, while docs/design-decisions.md credits the model. The README also describes an AI-DLC flow with your choices before code existed, while the design record says it was reconstructed after the code. These are statements about your own process, so you know which is true.

- A. Report them only; you correct the wording yourself
- B. Propose replacement wording in the review, and leave the README unchanged
- C. Edit the README to match docs/design-decisions.md
- D. Not yet defined
- X. Other (please specify)

[Answer]: X. Other: "Change the readme to make sure that the I am the one who decided everything". Follow-up (the person was told this would contradict D4 and D8 in docs/design-decisions.md, which credit the model): chose "Fix both files", i.e. confirmed they made those decisions; edit the README and also correct D4 and D8 in docs/design-decisions.md so they agree.

## Q3. [Developer] How much may the fixes change the Raft source in raft/?

The scan found no clear safety defect in raft/node.py. It did find places that behave differently under `python -O` (an `assert` in storage.py:45) and a crash on a protocol-impossible input (node.py:363).

- A. Do not change anything in raft/; report only
- B. Only changes that leave protocol behaviour as it is (for example replacing an `assert` with an explicit check)
- C. Any change the review justifies, including behaviour changes, each covered by a test
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Q4. [Quality] May the build step run the test suite and the mutation tool?

The scan only read the code, so the README figures (212 cases, 19 of 19 mutants caught, about 12 seconds for the suite) are unverified. The mutation tool runs up to four workers with a limit of 300 seconds per run.

- A. Run the test suite only
- B. Run the test suite and the mutation tool, before and after the fixes
- C. Run nothing
- D. Not yet defined
- X. Other (please specify)

[Answer]: A

## Consolidated Summary Confirmation

- Fixes to make: the mutation tool (baseline run, stop counting errors as caught), tests (negative tests for the invariant checker, storage tests), packaging (declare pytest, mypy config or drop the claim), docs (README and design record agree, list docs/ in the layout), and the linearizability test (guard or reword).
- Statements about who decided what: you confirmed you made those decisions, so the README is edited to say so and D4 and D8 in docs/design-decisions.md are corrected to agree.
- Raft source: nothing in raft/ is changed; findings there are reported only.
- Running: the test suite is run; the mutation tool is not.

Does this all look correct before I generate the requirements artifact?

- Looks correct
- Request changes

[Answer]: Looks correct
