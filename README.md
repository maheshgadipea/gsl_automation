# GSL Compliance Engine

> **System Architecture Specification — v21 (Final Reference-Model + Deterministic Audit Platform)**
>
> An enterprise compliance-testing platform for **1,500+ recurring regulatory and operational obligations**.
> The platform uses a **one-time, Admin-guided obligation onboarding** process to build an approved,
> versioned **Obligation Reference Model** from the real workpaper, Side-A entity evidence, and representative
> supporting documents. Future periods reuse that approved model: Admin refreshes Side-A facts when needed;
> the BU uploads period-specific supporting documents; the system validates evidence completeness; then a
> deterministic audit engine evaluates the stored assertions against typed facts and the time-aware Side-A master.
>
> **Core principle:**
>
> ```text
> FIRST TIME:
> Workpaper + real evidence + representative supporting documents
>             ↓
> AI-assisted reference-model construction
>             ↓
> Human confirmation
>             ↓
> Versioned APPROVED OBLIGATION MODEL
>
> FUTURE PERIODS:
> New Side-A evidence → refresh master facts
> New BU supporting documents → new run facts
>             ↓
> SAME APPROVED OBLIGATION MODEL
>             ↓
> DETERMINISTIC AUDIT
>             ↓
> PASS / FAIL / INDETERMINATE
> ```
>
> **No LLM, prompt, classifier, OCR output, or agent emits a compliance verdict.** AI may read, classify,
> extract, propose, and explain; deterministic code validates, commits approved configuration, computes facts,
> executes assertions, and produces the verdict.

---

## Contents

| § | Section |
|---|---|
| 1 | Executive summary |
| 2 | Design decisions from v1–v20 |
| 3 | Core mental model |
| 4 | Side-A / Side-B architecture |
| 5 | One-time obligation onboarding |
| 6 | Admin onboarding chatbot |
| 7 | Reference-model construction |
| 8 | Obligation model / Compliance Pack |
| 9 | Archetype — final role and whether it is mandatory |
| 10 | Role / Document Type / Canonical Field model |
| 11 | Assertion model |
| 12 | SOFTEX assertion construction example |
| 13 | Side-A master model |
| 14 | Side-A recurring refresh |
| 15 | BU runtime workflow |
| 16 | Supporting-document discovery and completeness |
| 17 | Document classification and role binding |
| 18 | Extraction, OCR and field translation |
| 19 | Normalization and Fact model |
| 20 | Deterministic audit engine |
| 21 | Five universal audit attributes |
| 22 | Primitive catalogue |
| 23 | Full end-to-end flow diagrams |
| 24 | Entity relationship model |
| 25 | Relational schema |
| 26 | SQL schema |
| 27 | AI agents and tool contracts |
| 28 | Technology stack and libraries |
| 29 | Package / repository structure |
| 30 | API and service boundaries |
| 31 | Auditability / MLOps / provenance |
| 32 | Security and determinism invariants |
| 33 | Testing strategy |
| 34 | SOFTEX test walkthrough |
| 35 | Quarterly reuse / replay |
| 36 | Governance and change management |
| 37 | Implementation plan |
| 38 | Definition of done |
| 39 | Final architectural decisions |
| 40 | Reference technology sources |

---

# 1. Executive summary

The platform has two user-facing portals and several controlled system services.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ADMIN PORTAL                                       │
│                                                                              │
│  ONE-TIME / CHANGE-TIME WORKFLOWS                                           │
│                                                                              │
│  1. Upload workpaper                                                        │
│       ↓                                                                      │
│     Create Compliance Pack DRAFT                                             │
│       ↓                                                                      │
│  2. Select obligation                                                       │
│       ↓                                                                      │
│  3. Upload Side-A evidence                                                  │
│       ↓                                                                      │
│     Build/update entity master facts                                        │
│       ↓                                                                      │
│  4. Upload representative previous supporting documents                     │
│       ↓                                                                      │
│     AI + deterministic compiler build reference model                       │
│       ↓                                                                      │
│     Admin confirms model                                                    │
│       ↓                                                                      │
│     Compliance Pack revision becomes ACTIVE                                 │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        APPROVED OBLIGATION MODEL                              │
│                                                                              │
│  Rules + assertions + roles + document types + field mappings + parameters  │
│  + evidence dependencies + execution contract + provenance                  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                           REUSED FOR EVERY PERIOD
                                       │
          ┌────────────────────────────┴───────────────────────────┐
          ▼                                                        ▼
┌──────────────────────────┐                         ┌──────────────────────────┐
│       ADMIN RUNTIME      │                         │        BU RUNTIME         │
│                          │                         │                          │
│ Select obligation        │                         │ Select obligation +      │
│ Upload new Side-A docs  │                         │ period                   │
│ Refresh historical      │                         │ Upload supporting docs   │
│ master facts            │                         │ Validate completeness    │
└────────────┬─────────────┘                         └────────────┬─────────────┘
             │                                                   │
             ▼                                                   ▼
      SIDE-A MASTER                                          SIDE-B FACTS
             │                                                   │
             └───────────────────────┬───────────────────────────┘
                                     ▼
                          DETERMINISTIC AUDIT ENGINE
                                     │
                                     ▼
                           PASS / FAIL / INDETERMINATE
```

## Primary architectural choice

The **approved obligation reference model** is the primary reusable asset for recurring audits.

An Archetype is an **optional but useful platform-level execution contract** when multiple obligations
share meaningful control semantics. It is **not required merely to group obligations**, and it is never
the source of the concrete BU document checklist.

If an initial deployment cannot prove meaningful cross-obligation execution reuse, the system may run
without Archetypes; the data model remains valid. If later evidence proves that a family shares execution
semantics, an Archetype can be introduced without changing the Compliance Pack's obligation-specific rules.

---

# 2. Design decisions from v1–v20

The final design incorporates the important lessons from earlier versions and testing conversations.

## 2.1 Deterministic verdict boundary

LLMs never emit PASS/FAIL/INDETERMINATE. The decision plane consumes persisted typed facts and approved
configuration only.

## 2.2 Side A vs Side B

- **Side A** = workpaper + durable entity evidence + historical master projection.
- **Side B** = period-specific supporting evidence supplied for the audit run.
- Side A is reused and versioned over time.
- Side B is new for each period/run.

## 2.3 Workpaper upload must be easy

Admin uploads the workpaper. The application creates the Compliance Pack. Admin does **not** need to
select an Archetype or manually design the database model as the first step.

## 2.4 Onboarding is a guided conversation

The Admin chatbot guides the user through:

```text
Workpaper
→ Side-A evidence
→ reference supporting evidence
→ generated model
→ questions / ambiguity resolution
→ confirmation
→ ACTIVE model
```

## 2.5 First occurrence teaches; later occurrences reuse

The system uses representative prior evidence to create the first approved obligation reference model.
Future quarters reuse that model rather than rediscovering document types, fields and assertions from scratch.

This is **reference-model onboarding**, not necessarily ML training.

## 2.6 Supporting-document requirements are learned from evidence + assertions

A workpaper statement such as “Invoice raised for export of service” must not cause the system to invent
`commercial_invoice` as a mandatory concrete document type.

During onboarding, real representative documents establish the concrete document types and schemas, while
compiled assertions establish the abstract evidence dependencies/roles.

## 2.7 BU sees only approved requirements

At runtime, BU selects the onboarded obligation. The system loads the **approved model** and requests only
the supporting evidence defined by that model.

## 2.8 Evidence completeness gates audit

No audit starts until all blocking evidence requirements are satisfied and the evidence set is locked.

## 2.9 Side-A master is time-aware

No overwrite-in-place. Facts have provenance and validity windows; the master is a projection/query over them.

## 2.10 Archetype is not a mandatory user concept

BU never selects an Archetype. Admin onboarding can use an Archetype internally if one is proven useful,
but the approved Compliance Pack remains the primary obligation object.

---

# 3. Core mental model

Use these definitions consistently in code, UI, database and documentation.

| Object | Meaning |
|---|---|
| **Obligation** | A single business/regulatory use case to be tested |
| **Compliance Pack** | Versioned configuration of one obligation |
| **Reference Model** | The approved operational model produced during first-time onboarding; stored primarily as the pack revision plus its linked registries/rules |
| **Role** | The job an evidence artifact performs in an obligation |
| **Document Type** | What a concrete artifact is |
| **Document Field** | A field physically/semantically present on a document type |
| **Canonical Field** | Global meaning of an extracted value |
| **Assertion** | A structured, executable statement the obligation requires the system to prove |
| **Primitive** | Atomic deterministic operation used by an assertion |
| **Archetype** | Optional reusable control-family execution contract |
| **Side-A Fact** | Entity/master fact derived from authoritative evidence |
| **Side-B Fact** | Period/run fact derived from supporting documents |
| **Run** | One execution of one obligation revision for one period |
| **Verdict** | Deterministic PASS / FAIL / INDETERMINATE result |

The conceptual chain is:

```text
WORKPAPER
   ↓
COMPLIANCE PACK / REFERENCE MODEL
   ↓
ASSERTIONS
   ↓
REQUIRED EVIDENCE DEPENDENCIES
   ↓
ROLES
   ↓
DOCUMENT TYPES
   ↓
DOCUMENT FIELDS
   ↓
CANONICAL FIELDS
   ↓
FACTS
   ↓
DETERMINISTIC EVALUATION
   ↓
VERDICT
```

---

# 4. Side-A / Side-B architecture

## 4.1 Side A

Side A answers:

> **What authoritative state does the entity have, and what baseline/configuration should this obligation be judged against?**

Side-A contents include:

- Compliance Pack and its approved assertions;
- statutory parameters;
- entity identity;
- registrations;
- authorised signatories;
- approval matrices;
- other durable baseline values derived from authoritative documents.

Side-A evidence enters through the same classification/extraction/normalization pipeline as Side-B evidence,
but the resulting facts are assigned entity scope and validity windows and contribute to master projections.

## 4.2 Side B

Side B answers:

> **What happened in this audit period, and what evidence proves it?**

Side-B examples:

- SOFTEX form;
- invoice;
- acknowledgement;
- bank evidence;
- working file;
- ledger;
- approval evidence.

Each run receives a fresh Side-B evidence set.

## 4.3 Formula

```text
        SIDE A                                    SIDE B
┌──────────────────────────┐              ┌──────────────────────────┐
│ Approved obligation      │              │ Period-specific evidence │
│ Side-A master facts     │              │ Extracted facts          │
│ Historical validity     │              │ Document provenance      │
│ Parameters              │              │                          │
└────────────┬─────────────┘              └─────────────┬────────────┘
             │                                          │
             └──────────────────┬───────────────────────┘
                                ▼
                      DETERMINISTIC AUDIT
                                │
                                ▼
                   PASS / FAIL / INDETERMINATE
```

---

# 5. One-time obligation onboarding

The first occurrence of an obligation is handled differently from future periods.

## 5.1 First-time onboarding flow

```text
ADMIN
  │
  ▼
┌─────────────────────────────┐
│ 1. Upload Workpaper         │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Create Compliance Pack      │
│ status = DRAFT              │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 2. Select newly created     │
│    obligation for onboarding│
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 3. Upload Side-A evidence   │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Build / refresh master      │
│ facts + provenance          │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ 4. Upload representative    │
│    previous supporting docs │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Reference-model compiler    │
│ • document types            │
│ • roles                     │
│ • field mappings            │
│ • assertions                │
│ • evidence dependencies     │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│ Admin review / confirmation │
└──────────────┬──────────────┘
               ▼
       ACTIVE PACK REVISION
```

## 5.2 Why representative supporting documents are valuable

A workpaper often names evidence abstractly. A real document tells the platform what the artifact actually
looks like and what fields it contains.

Example:

```text
Workpaper text:
    “Invoice raised for export of service.”

Representative document:
    Actual invoice PDF

System learns/proposes:
    role                = source_document
    document_type       = commercial_invoice (PROPOSAL)
    fields              = Invoice No / Invoice Date / Value / Currency / Customer
    canonical mappings  = invoice.number / invoice.date / population.item_amount / ...

Admin confirmation:
    ACCEPT / CORRECT / REJECT
```

The concrete document type is therefore **evidence-grounded**, not guessed from a phrase in the workpaper.

## 5.3 Onboarding output

The end product is an **approved obligation reference model**:

```text
SOFTEX MODEL v1
├── Compliance Pack metadata
├── approved Archetype reference (optional)
├── required roles
├── role → accepted document type bindings
├── document type definitions
├── document field definitions/mappings
├── canonical field dependencies
├── assertions / rules
├── parameters
├── Side-A master dependencies
├── supporting-evidence dependencies
└── complete provenance / confirmation record
```

---

# 6. Admin onboarding chatbot

The chatbot is a **workflow/orchestration agent**, not an autonomous compliance decision maker.

## 6.1 Entry screen

```text
Admin Assistant

What would you like to do?

[ Create New Obligation ]
[ Onboard / Refresh Existing Obligation ]
```

### Create New Obligation

```text
Upload workpaper → parse → create Compliance Pack → guide evidence onboarding
```

### Onboard / Refresh Existing Obligation

```text
Select obligation → upload evidence → reconcile → propose model/fact changes → confirm
```

## 6.2 Chatbot behavior

The chatbot should:

- explain what it has found;
- distinguish fact from proposal;
- ask one blocking question at a time where possible;
- show the exact structured value it intends to write;
- show source document/page/cell for the proposal;
- require explicit confirmation for durable configuration;
- never invent a concrete document requirement silently;
- never emit an audit verdict.

## 6.3 Read-back control

```text
Admin response
     ↓
AI interpretation
     ↓
Typed candidate
     ↓
Deterministic validation
     ↓
Read-back UI
 ┌─────────────────────────────────────┐
 │ What I understood: ...              │
 │ What will be written: ...           │
 │ Source: file/page/cell ...          │
 │                                     │
 │ [Confirm] [Correct]                 │
 └─────────────────────────────────────┘
     ↓
Commit only after confirmation
```

## 6.4 Chatbot should expose uncertainty types

```text
ARCHETYPE_FIT
NEW_CANONICAL_FIELD
DOCUMENT_TYPE_AMBIGUOUS
ROLE_AMBIGUOUS
RULE_BRANCH
PARAMETER_MISSING
SIDE_A_MASTER_CONFLICT
REFERENCE_MODEL_CONFLICT
ASSERTION_AMBIGUOUS
```

## 6.5 Tool calling rule

The LLM may call tools only through typed, allow-listed tool adapters.

```text
LLM
 ↓
Tool schema
 ↓
Typed request validation
 ↓
Service function
 ↓
Transactional DB write
 ↓
Audit log
```

The LLM must never receive arbitrary SQL or a generic “write to database” tool.

---

# 7. Reference-model construction

This is the central new operating model.

## 7.1 Reference-model construction stages

```text
WORKPAPER
    ↓
Extract obligation metadata + test steps
    ↓
Extract/normalize representative Side-A evidence
    ↓
Extract/normalize representative supporting evidence
    ↓
Create candidate Document Types
    ↓
Create candidate Roles
    ↓
Create candidate Document Fields
    ↓
Reuse / propose Canonical Fields
    ↓
Bind printed fields to canonical fields
    ↓
Compile Test Steps → Assertions
    ↓
Resolve assertion dependencies
    ↓
Derive required evidence roles
    ↓
Link roles to registered document types
    ↓
Admin confirmation
    ↓
Freeze approved model revision
```

## 7.2 Assertions are the bridge between workpaper and evidence

A test-step sentence is transformed into a structured assertion.

Example:

```text
Workpaper:
“SOFTEX invoice value agrees with invoice raised for export service.”

↓

Assertion:
attribute = accuracy
primitive = value_equals

left:
  role = filing_form
  field = population.item_amount

right:
  role = source_document
  field = population.item_amount
```

Now the system can determine that the assertion depends on two evidence roles:

```text
filing_form
source_document
```

It can then look for registered representative documents that satisfy those roles.

## 7.3 No manual “supporting document list” is required in the normal onboarding path

The Admin supplies representative real documents. The system proposes the model. The Admin confirms.

This avoids forcing the Admin to guess every future document type before seeing a real example.

## 7.4 Model versioning

Each approved reference model is immutable.

```text
SOFTEX
  v1 ACTIVE
  v2 DRAFT
  v3 RETIRED
```

A change to an assertion, binding, field mapping, parameter or execution contract creates a new revision.
Historical runs reference exactly the revision used for the audit.

---

# 8. Obligation model / Compliance Pack

## 8.1 Compliance Pack = primary reusable obligation model

The Compliance Pack is the anchor for everything specific to one obligation.

Example:

```text
LLTC_70
SOFTEX Reporting
revision = 1
status = ACTIVE
```

It owns or references:

- workpaper provenance;
- assertions/rules;
- parameters;
- required evidence roles;
- accepted document-type bindings;
- Side-A master dependencies;
- owner / approver / frequency;
- model revision;
- optional Archetype reference;
- onboarding provenance.

## 8.2 Why a Compliance Pack remains necessary

Even with a generic engine, each obligation must remember:

```text
WHAT IS THIS OBLIGATION?
WHAT RULES DOES IT HAVE?
WHAT PARAMETERS APPLY?
WHICH EVIDENCE ROLES ARE REQUIRED?
WHICH DOCUMENT TYPES SATISFY THOSE ROLES?
WHICH MASTER FIELDS DOES IT REFERENCE?
WHICH VERSION WAS APPROVED?
```

That is the job of the Compliance Pack.

---

# 9. Archetype — final role and whether it is mandatory

## 9.1 The honest conclusion

After the reference-model onboarding approach, the Archetype is **optional**.

You should keep it only when there is proven, repeated **execution behavior** across obligations.

Do not keep it merely to create a grouping hierarchy.

## 9.2 If an Archetype is used

It provides:

```text
shared control topology
supported evidence roles
allowed primitive grammar
common lifecycle semantics
missing-data semantics
execution restrictions
common trace requirements
versioned shared behavior
```

Example:

```text
periodic_filing@2.0.1
    │
    ├── SOFTEX pack
    ├── GST pack
    ├── TDS return pack
    └── FLA pack
```

The SOFTEX pack still owns its own assertions.

## 9.3 If no proven reuse exists

The system may omit Archetypes:

```text
Compliance Pack
      ↓
Assertions
      ↓
Primitives
      ↓
Facts
      ↓
Deterministic evaluator
```

The platform must not create empty or artificial Archetypes just to satisfy an architectural diagram.

## 9.4 BU never sees Archetypes

BU selects:

```text
SOFTEX — Q3 FY2026
```

not:

```text
periodic_filing
```

---

# 10. Role / Document Type / Canonical Field model

## 10.1 Role

A role is an abstract evidence purpose.

```text
filing_form
source_document
acknowledgement
bank_submission
approval
population_file
```

## 10.2 Document Type

A document type is a concrete artifact category.

```text
softex_form
commercial_invoice
stpi_ack
ad_bank_submission
softex_working_file
```

## 10.3 Canonical Field

A canonical field is global semantic vocabulary.

```text
party.iec
party.legal_name
invoice.number
invoice.date
population.item_amount
filing.submitted_at
signature.valid
signature.signer
```

## 10.4 Relationships

```text
ROLE
 │
 │ capability
 ▼
ROLE_CANONICAL_FIELD
 │
 ▼
CANONICAL_FIELD

COMPLIANCE PACK
 │
 │ required role
 ▼
PACK_ROLE
 │
 │ accepted concrete type
 ▼
DOCUMENT_TYPE
 │
 ▼
DOCUMENT_TYPE_FIELD
 │
 ▼
CANONICAL_FIELD
```

The same role can map to different concrete document types in different obligations.

Example:

```text
filing_form
   ├── SOFTEX pack → softex_form
   ├── GST pack    → gstr3b_form
   └── TDS pack    → tds_return
```

---

# 11. Assertion model

An assertion is the machine-readable realization of one workpaper test step.

## 11.1 Assertion fields

```text
assertion_id
rule_code
pack_id
pack_revision
attribute
primitive
severity
arguments
expected/relationship metadata
required role dependencies
required Side-A master dependencies
on_fail text
sequence
source provenance
```

## 11.2 Assertion dependency model

```text
Assertion
   │
   ├── Side-B role dependencies
   │      ├── filing_form
   │      └── source_document
   │
   ├── Side-A dependencies
   │      └── company_master.iec
   │
   ├── parameters
   │      └── due_days_offset
   │
   └── primitive
          └── date_within_n_days
```

## 11.3 Evidence discovery from assertions

The platform derives a **logical evidence contract** from assertion dependencies:

```text
ALL ACTIVE ASSERTIONS
       ↓
collect distinct Side-B roles
       ↓
collect distinct required fields
       ↓
deduplicate
       ↓
required evidence-role set
```

This is more robust than guessing document names from narrative text.

Concrete document types are then resolved from the approved onboarding reference model.

---

# 12. SOFTEX assertion construction example

Assume the workpaper contains these conceptual tests.

## 12.1 Completeness

### CMP-01

```yaml
attribute: completeness
primitive: documents_present
required_roles:
  - filing_form
```

### CMP-02

```yaml
attribute: completeness
primitive: documents_present
required_roles:
  - source_document
```

### CMP-03

```yaml
attribute: completeness
primitive: documents_present
required_roles:
  - acknowledgement
```

## 12.2 Correctness

### COR-01 — Entity identity

```yaml
attribute: correctness
primitive: matches_master
actual:
  role: filing_form
  field: party.iec
master:
  field: party.iec
```

### COR-02 — Customer identity

```yaml
attribute: correctness
primitive: value_equals
left:
  role: filing_form
  field: counterparty.legal_name
right:
  role: source_document
  field: counterparty.legal_name
```

## 12.3 Accuracy

### ACC-01 — Amount reconciliation

```yaml
attribute: accuracy
primitive: value_equals
left:
  role: filing_form
  field: population.item_amount
right:
  role: source_document
  field: population.item_amount
```

### ACC-02 — Working-file tie-out

```yaml
attribute: accuracy
primitive: sum_equals
left:
  role: population_file
  field: population.item_amount
right:
  role: filing_form
  field: population.total_amount
```

### ACC-03 — FX calculation

```yaml
attribute: accuracy
primitive: arithmetic_expression
inputs:
  foreign_amount:
    role: filing_form
    field: population.foreign_amount
  fx_rate:
    role: filing_form
    field: population.fx_rate
expected:
  role: filing_form
  field: population.inr_amount
```

## 12.4 Timeliness

### TIM-01

```yaml
attribute: timeliness
primitive: date_within_n_days
action_date:
  role: filing_form
  field: filing.submitted_at
trigger_date:
  role: source_document
  field: invoice.date
parameter: due_days_offset
calendar: statutory_calendar
```

## 12.5 Authorization & Review

### AUT-01

```yaml
attribute: authorization_and_review
primitive: signature_valid
role: filing_form
```

### AUT-02

```yaml
attribute: authorization_and_review
primitive: signer_authorized
signer:
  role: filing_form
  field: signature.signer
signed_at:
  role: filing_form
  field: signature.signed_at
master:
  company_signatory
```

### AUT-03

```yaml
attribute: authorization_and_review
primitive: maker_checker_distinct
maker:
  role: population_file
  field: population.maker
checker:
  role: approval
  field: approval.checker
```

## 12.6 Derived logical supporting evidence roles

From all assertions, the platform can derive:

```text
filing_form
source_document
acknowledgement
population_file
approval
```

It then resolves concrete document types from the **approved onboarding reference model** rather than inventing them from text.

---

# 13. Side-A master model

## 13.1 What belongs in Side-A master

Only durable/entity-scoped truth.

Examples:

```text
party.legal_name
party.iec
party.pan
party.gstin
registration.lop_number
registration.status
bank.ad_code
company_signatory
approval_matrix
```

## 13.2 What does NOT belong in Side-A master

Period-specific values such as:

```text
invoice.amount
SOFTEX.submission_date
Q3 working-file total
Q3 bank realisation
Q3 acknowledgement number
```

Those become Side-B run facts.

## 13.3 Master is a projection, not mutable truth

Historical facts remain append-only.

```text
raw Side-A facts
     ↓
validity / conflict resolution
     ↓
company_master projection
```

Historical runs refer to historical truth.

---

# 14. Side-A recurring refresh

For a new quarter:

```text
ADMIN
  ↓
Select SOFTEX
  ↓
Upload new / changed Side-A evidence
  ↓
Classify
  ↓
Extract
  ↓
Normalize
  ↓
Compare against historical facts
```

Then:

```text
No prior value     → ADD
Same value         → RECONFIRM
New non-overlapping validity → SUPERSEDE
Overlapping conflict → HUMAN REVIEW
```

Example:

```text
Q2 signatory:
Raj Kumar
valid_to = 2026-06-30

Q3 signatory:
Priya Sharma
valid_from = 2026-07-01
```

A Q3 run dated after 2026-07-01 uses Priya's Side-A truth; a historical Q2 run continues to resolve Raj's validity.

---

# 15. BU runtime workflow

```text
BU
 │
 ▼
Select onboarded obligation
 │
 ▼
Select period
 │
 ▼
System loads ACTIVE Compliance Pack revision
 │
 ▼
Build supporting-document checklist from approved reference model
 │
 ▼
BU uploads one or more documents
 │
 ▼
Classify
 │
 ▼
Validate document type against expected binding
 │
 ▼
Bind document to role
 │
 ▼
Repeat until evidence complete
 │
 ▼
Evidence lock
 │
 ▼
Extract / normalize Side-B facts
 │
 ▼
Run assertions
 │
 ▼
PASS / FAIL / INDETERMINATE
```

## 15.1 Wrong-document scenario

Expected:

```text
source_document → commercial_invoice
```

BU uploads:

```text
ad_bank_realisation.pdf
```

System outcome:

```text
classification = VALID document type
role satisfaction = FAIL
missing role = source_document
completeness = FALSE
run status = COLLECTING
```

The file is retained for provenance, but it cannot satisfy the invoice/source-document dependency.

---

# 16. Supporting-document discovery and completeness

The system should **not ask Admin to manually enumerate every supporting document** if onboarding already has representative evidence.

Instead:

```text
REFERENCE SUPPORTING DOCUMENTS
          ↓
registered document types
          ↓
compiled assertions
          ↓
required evidence roles
          ↓
approved role → document bindings
          ↓
future BU checklist
```

## 16.1 Completeness gate

```text
required role set
       ⊆
accepted role set
       AND
all blocking field dependencies satisfied
       AND
no unresolved classification/binding blockers
       ↓
EVIDENCE_COMPLETE = TRUE
```

Until TRUE:

```text
AUDIT = BLOCKED
```

## 16.2 Optional evidence

A role may be:

```text
required = FALSE
```

or represented as a conditional dependency:

```text
if assertion branch applies:
    role required
else:
    role not applicable
```

The condition must be deterministic and part of the approved model.

---

# 17. Document classification and role binding

## 17.1 Classification signals

Recommended multi-signal pipeline:

```text
OCR / native text
       +
layout / geometry
       +
registry hints
       +
filename/metadata (low-weight)
       ↓
fusion
       ↓
document_type candidate + confidence
```

The current architecture preserves the important rule that learned classification is only one signal;
registered `classify_hints` provide deterministic anchors.

## 17.2 Binding

At runtime, the system does:

```text
detected document_type
        ↓
find pack-approved bindings
        ↓
find role(s) the type can satisfy
        ↓
select the appropriate open role
        ↓
record role binding
```

A type that is not registered/approved for the selected pack cannot silently redefine the evidence contract.

## 17.3 Classification status values

```text
PENDING
CANDIDATE
AUTO_ACCEPTED
REVIEW_REQUIRED
REJECTED
BOUND
UNBOUND
```

---

# 18. Extraction, OCR and field translation

## 18.1 Extraction cascade

Use the cheapest deterministic method first.

```text
Native structured parser?
      │ YES → parse directly
      │ NO
      ▼
Native PDF text?
      │ YES → PyMuPDF text extraction
      │ NO / weak
      ▼
OCR required?
      │ YES → OCR engine
      ▼
Layout / table parser
      ▼
LLM key-value extraction
      ▼
Typed candidate values
```

The platform should OCR only when needed because OCR can be substantially slower than native extraction;
PyMuPDF's current documentation explicitly recommends detecting whether OCR is beneficial and reusing the OCR text page for subsequent extraction. citeturn784546search1

## 18.2 PDF

Recommended baseline: **PyMuPDF** for native text, page geometry and PDF rendering. PyMuPDF documents `Page.get_text()` and OCR integration through `get_textpage_ocr()`; OCR is based on Tesseract in its integrated OCR path. citeturn784546search7turn784546search1

## 18.3 OCR

Recommended evaluation candidates:

### Tesseract

Use for:

- standard scanned documents;
- controlled languages;
- deterministic local fallback.

PyMuPDF supports OCR through Tesseract when it is installed with the appropriate language data. citeturn784546search8

### PaddleOCR

Use for:

- complex scans;
- screenshots;
- tables/layout-heavy documents;
- multilingual/modern document parsing.

PaddleOCR's current pipeline documentation supports multiple OCR model generations, and its 2026 documentation describes a document-parsing model family for complex real-world layouts. citeturn784546search2turn784546search6

**Do not hard-code one OCR vendor into the data model.** The `extractor_hash` and `method` identify the implementation actually used.

## 18.4 Spreadsheet parsing

Use **openpyxl** for `.xlsx/.xlsm` workpapers and structured supporting spreadsheets. It supports reading/writing Excel 2010+ OOXML files and worksheet/cell access. citeturn514786search13

Primary functions:

```python
openpyxl.load_workbook()
Workbook()
worksheet.iter_rows()
worksheet.cell()
```

## 18.5 Word / other formats

Use a dedicated parser appropriate to the format:

- DOCX → `python-docx`;
- PPTX → `python-pptx` if required;
- raw email/message exports → structured parser;
- images → Pillow/OpenCV + OCR;
- scanned PDFs → PyMuPDF rendering + OCR.

Use parser selection by MIME/document type, not by filename extension alone.

## 18.6 LLM extraction

The LLM should receive a bounded extraction task:

```text
Document bytes / OCR representation
      ↓
Prompt + schema
      ↓
Typed extraction proposal
      ↓
JSON schema validation
      ↓
Fact candidate
```

The LLM should not:

- choose a final verdict;
- invent missing values;
- invent a document type not in the registry;
- invent canonical fields;
- mutate master data directly.

---

# 19. Normalization and Fact model

## 19.1 Types

| Type | Runtime | Rule |
|---|---|---|
| string | Python `str` | NFKC, whitespace normalization |
| number | `Decimal` | arbitrary precision; never IEEE-754 float |
| date | `datetime.date` | explicit accepted formats; ambiguity = INDETERMINATE |
| boolean | tri-state | unknown ≠ false |

## 19.2 Fact provenance

Every fact should be traceable to:

```text
document_id
page
bounding box / coordinates
raw text
matched label
canonical field
confidence
extraction method
extractor hash
model/prompt version if AI was involved
created_at
validity window if Side A
run_id if Side B
```

Example:

```json
{
  "fact_id": "...",
  "side": "SIDE_B",
  "run_id": "RUN-Q3-001",
  "document_id": "DOC-001",
  "role_id": "filing_form",
  "canonical_field_id": "population.item_amount",
  "value": {"decimal": "25000.00"},
  "confidence": "0.9840",
  "method": "vision_llm",
  "provenance": {
    "page": 1,
    "bbox": [412,318,596,341],
    "raw_text": "25,000.00",
    "matched_label": "Invoice Value",
    "extractor_hash": "..."
  }
}
```

---

# 20. Deterministic audit engine

The engine is a **closed world**.

Inputs:

```text
approved pack revision
approved assertions
approved role/document bindings
typed Side-B facts
historical Side-A master projection
statutory calendar
approved parameters
```

Prohibited:

```text
LLM calls
network access
filesystem access
wall clock
randomness
float arithmetic
arbitrary Python calls
unbound names
```

## 20.1 Restricted AST

Use a whitelist parser/evaluator.

Allow only explicitly approved constructs such as:

```text
Compare
BoolOp
BinOp
UnaryOp
Name
Constant
```

Reject:

```text
Call
Attribute
comprehension
import
lambda
arbitrary subscript semantics if not explicitly allowed
float literals
```

## 20.2 Deterministic result states

```text
PASS
FAIL
INDETERMINATE
```

Never turn an unsafe or missing condition into `False`.

---

# 21. Five universal audit attributes

Every obligation has a common reporting vocabulary, even though individual assertions differ.

## 21.1 Completeness

Questions:

- Are all required evidence roles satisfied?
- Is the required population present?
- Does the evidence cover the required period?

Primitives:

```text
documents_present
field_present
population_defined
set_equality
period_covers
```

## 21.2 Correctness

Questions:

- Is the right entity identified?
- Does the evidence agree with the authoritative master?
- Does the statutory identity/section/reference match?

Primitives:

```text
matches_master
value_equals
regex_match
reference_present_in_document
```

## 21.3 Accuracy

Questions:

- Do amounts reconcile?
- Do line items sum to totals?
- Are rates/FX calculations correct?
- Are unexplained adjustments or duplicates present?

Primitives:

```text
sum_equals
arithmetic_expression
rate_applied_correctly
fx_rate_plausible
no_unexplained_adjustments
no_duplicates
```

## 21.4 Timeliness

Questions:

- Was the action completed by the statutory deadline?
- Did one event precede another?
- Did the required status occur within the permitted window?

Primitives:

```text
date_on_or_before
date_within_n_days
status_in_or_pending_within
period_covers
```

## 21.5 Authorization & Review

Questions:

- Is the signature cryptographically valid?
- Was the signer authorised as of the event date?
- Are maker/checker identities distinct?
- Did review precede the controlled action?

Primitives:

```text
signature_valid
signer_authorized
maker_checker_distinct
date_on_or_before
```

## 21.6 Rollup

```text
ANY FAIL → FAIL
ELSE ANY INDETERMINATE → INDETERMINATE
ELSE → PASS
```

The rollup must preserve individual step results and trace references.

---

# 22. Primitive catalogue

The primitive catalogue is independent of any single obligation.

## Evidence

```text
documents_present
field_present
```

## Population

```text
population_defined
set_equality
no_duplicates
period_covers
```

## Comparison

```text
value_equals
matches_master
regex_match
reference_present_in_document
```

## Arithmetic

```text
sum_equals
arithmetic_expression
rate_applied_correctly
fx_rate_plausible
no_unexplained_adjustments
```

## Time

```text
date_on_or_before
date_within_n_days
status_in_or_pending_within
```

## Authorization

```text
signature_valid
signer_authorized
maker_checker_distinct
```

Every primitive must define:

```text
input contract
output type
missing-input behavior
invalid-input behavior
trace semantics
unit tests
property tests where applicable
```

---

# 23. Full end-to-end flow diagrams

## 23.1 First-time onboarding

```text
┌──────────────┐
│    ADMIN     │
└──────┬───────┘
       │ upload workpaper
       ▼
┌──────────────────────┐
│ WORKPAPER PARSER     │  openpyxl
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ COMPLIANCE PACK DRAFT│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Side-A evidence      │
│ onboarding           │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ MASTER FACTS         │
│ + provenance         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Representative       │
│ supporting docs      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ AI + compiler        │
│ reference model      │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Admin confirmation   │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ PACK REVISION ACTIVE │
└──────────────────────┘
```

## 23.2 Future BU audit

```text
BU
 ↓ select onboarded obligation + period
 ↓
load ACTIVE PACK REVISION
 ↓
derive checklist from approved evidence dependencies / bindings
 ↓
upload supporting documents
 ↓
classify
 ↓
bind roles
 ↓
completeness gate
 ├── no → request missing / replace wrong docs
 └── yes
      ↓
   lock evidence
      ↓
   extract + normalize facts
      ↓
   Side-B facts + historical Side-A master
      ↓
   assertion engine
      ↓
   step results / trace
      ↓
   overall verdict
```

## 23.3 Full platform picture

```text
                       ┌────────────────────────┐
                       │       ADMIN CHATBOT     │
                       └───────────┬────────────┘
                                   │
                     ┌─────────────┴──────────────┐
                     │                            │
                     ▼                            ▼
               Workpaper                    Existing pack
                     │                            │
                     ▼                            ▼
               Pack creation              Refresh onboarding
                     │                            │
                     └─────────────┬──────────────┘
                                   ▼
                          Approved model revision
                                   │
                  ┌────────────────┼─────────────────┐
                  ▼                                  ▼
          ADMIN SIDE-A RUNTIME                BU SIDE-B RUNTIME
                  │                                  │
          new evidence                           new docs
                  │                                  │
                  ▼                                  ▼
          master fact lifecycle             classify/bind/extract
                  │                                  │
                  └────────────────┬─────────────────┘
                                   ▼
                          COMPLETENESS GATE
                                   │
                                   ▼
                         DETERMINISTIC ENGINE
                                   │
                                   ▼
                              VERDICT
```

---

# 24. Entity relationship model

## 24.1 Logical ERD

```text
                         ┌──────────────────────┐
                         │       ARCHETYPE      │
                         │  optional pattern    │
                         └──────────┬───────────┘
                                    │ 1:N
                                    ▼
                     ┌────────────────────────────┐
                     │ ARCHETYPE_SUPPORTED_ROLE  │
                     └─────────────┬──────────────┘
                                   N:1
                                    ▼
                           ┌──────────────────┐
                           │   ROLE_REGISTRY  │
                           └────────┬─────────┘
                                   N:M
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │ ROLE_CANONICAL_FIELD  │
                        └────────────┬───────────┘
                                    N:1
                                     ▼
                           ┌──────────────────┐
                           │ CANONICAL_FIELD  │
                           └──────────────────┘

ARCHETYPE (optional)
      │ 1:N
      ▼
┌──────────────────────┐
│    COMPLIANCE_PACK   │──────────────┐
└───────┬──────────────┘              │
        │ 1:N                         │ 1:N
        ▼                             ▼
┌──────────────────────┐       ┌──────────────────────┐
│  COMPLIANCE_ROLE    │       │   COMPLIANCE_RULE    │
└────────┬─────────────┘       └──────────┬───────────┘
         │ N:1                            │ N:1
         ▼                                ▼
 DOCUMENT_TYPE                     PRIMITIVE CATALOGUE
         │
         │ 1:N
         ▼
 DOCUMENT_TYPE_FIELD
         │ N:1
         ▼
 CANONICAL_FIELD

COMPLIANCE_PACK
      │ 1:N
      ▼
    RUN
      │ 1:N
      ▼
  DOCUMENT
      │ 1:N
      ▼
    FACT
      │
      └──────────────► CANONICAL_FIELD

COMPANY_MASTER
      │ 1:N
      ├──────────────► COMPANY_SIGNATORY
      │
      └──────────────► SIDE-A FACT / validity history

RUN + RULE + FACT + MASTER
            │
            ▼
       STEP_RESULT
            │ 1:N
            ▼
      RULE_COMPARISON
```

## 24.2 Cardinality summary

| Relationship | Cardinality |
|---|---:|
| Archetype → Supported Roles | 1:N |
| Role ↔ Canonical Field | N:M |
| Archetype → Compliance Packs | 1:N (optional feature) |
| Compliance Pack → Required Roles | 1:N |
| Compliance Pack → Rules | 1:N |
| Compliance Pack → Runs | 1:N |
| Document Type → Document Fields | 1:N |
| Compliance Pack Role → Document Type | N:1 |
| Run → Documents | 1:N |
| Document → Facts | 1:N |
| Canonical Field → Facts | 1:N |
| Company Master → Signatories | 1:N |
| Rule → Step Results | 1:N across runs |

---

# 25. Relational schema

The schema is deliberately optimized around a small number of durable core objects.

## Core tables

```text
archetype
role_registry
archetype_supported_role
canonical_field
role_canonical_field
company_master
company_signatory
document_type
document_type_field
compliance_pack
compliance_pack_role
compliance_rule
run
document
fact
step_result
rule_comparison
onboarding_question
onboarding_model_snapshot
```

### Why `onboarding_model_snapshot` exists

The approved model should be exportable and hashable as one immutable configuration snapshot.
That snapshot is what lets a historical run be replayed even if registries later evolve.

---

# 26. SQL schema

```sql
CREATE TABLE archetype (
    archetype_id       VARCHAR(80) PRIMARY KEY,
    slug               VARCHAR(60) NOT NULL,
    version            VARCHAR(20) NOT NULL,
    name               VARCHAR(200) NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    execution_contract JSONB NOT NULL,
    allowed_primitives JSONB NOT NULL,
    status             VARCHAR(20) NOT NULL
                       CHECK (status IN ('DRAFT','ACTIVE','RETIRED')),
    effective_from     DATE,
    effective_to       DATE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (slug, version)
);

CREATE TABLE role_registry (
    role_id       VARCHAR(80) PRIMARY KEY,
    name          VARCHAR(160) NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    status        VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE archetype_supported_role (
    archetype_id VARCHAR(80) NOT NULL REFERENCES archetype(archetype_id),
    role_id      VARCHAR(80) NOT NULL REFERENCES role_registry(role_id),
    PRIMARY KEY (archetype_id, role_id)
);

CREATE TABLE canonical_field (
    canonical_field_id VARCHAR(80) PRIMARY KEY,
    namespace          VARCHAR(40) NOT NULL,
    name               VARCHAR(80) NOT NULL,
    data_type          VARCHAR(20) NOT NULL
                       CHECK (data_type IN ('string','number','date','boolean')),
    description        TEXT NOT NULL DEFAULT '',
    status             VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (namespace, name)
);

CREATE TABLE role_canonical_field (
    role_id             VARCHAR(80) NOT NULL REFERENCES role_registry(role_id),
    canonical_field_id  VARCHAR(80) NOT NULL REFERENCES canonical_field(canonical_field_id),
    usage_purpose       VARCHAR(240),
    PRIMARY KEY (role_id, canonical_field_id)
);

CREATE TABLE company_master (
    entity_id            VARCHAR(80) PRIMARY KEY,
    legal_name           VARCHAR(240) NOT NULL,
    taxpayer_identifier  VARCHAR(80),
    pan                  VARCHAR(80),
    gstin                VARCHAR(80),
    iec                  VARCHAR(80),
    cin                  VARCHAR(80),
    registrations        JSONB NOT NULL DEFAULT '{}'::jsonb,
    approval_matrix      JSONB NOT NULL DEFAULT '{}'::jsonb,
    status               VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE company_signatory (
    signatory_id BIGSERIAL PRIMARY KEY,
    entity_id    VARCHAR(80) NOT NULL REFERENCES company_master(entity_id),
    name         VARCHAR(200) NOT NULL,
    role         VARCHAR(120),
    valid_from   DATE,
    valid_to     DATE,
    source_ref   JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE document_type (
    document_type_id   VARCHAR(80) PRIMARY KEY,
    doc_type_code      VARCHAR(100) NOT NULL UNIQUE,
    name               VARCHAR(240) NOT NULL,
    issuer_authority   VARCHAR(200),
    category           VARCHAR(120),
    supported_formats  JSONB NOT NULL DEFAULT '[]'::jsonb,
    parser             VARCHAR(40),
    classify_hints     JSONB NOT NULL DEFAULT '[]'::jsonb,
    status             VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE document_type_field (
    document_type_field_id BIGSERIAL PRIMARY KEY,
    document_type_id       VARCHAR(80) NOT NULL REFERENCES document_type(document_type_id),
    field_code             VARCHAR(120) NOT NULL,
    field_label            VARCHAR(240) NOT NULL,
    canonical_field_id     VARCHAR(80) NOT NULL REFERENCES canonical_field(canonical_field_id),
    data_type              VARCHAR(20) NOT NULL,
    selector               VARCHAR(240),
    repeating              BOOLEAN NOT NULL DEFAULT FALSE,
    mandatory              BOOLEAN NOT NULL DEFAULT TRUE,
    transformation_rule    TEXT,
    version                VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_type_id, field_code)
);

CREATE TABLE compliance_pack (
    pack_id          VARCHAR(80) NOT NULL,
    revision         INTEGER NOT NULL,
    name             VARCHAR(240) NOT NULL,
    archetype_id     VARCHAR(80) REFERENCES archetype(archetype_id),
    entity_id        VARCHAR(80) REFERENCES company_master(entity_id),
    description      TEXT NOT NULL DEFAULT '',
    frequency        VARCHAR(30) NOT NULL,
    jurisdiction     VARCHAR(80),
    owner            VARCHAR(160) NOT NULL,
    approver         VARCHAR(160),
    status           VARCHAR(20) NOT NULL
                     CHECK (status IN ('DRAFT','REVIEW','SHADOW','ACTIVE','RETIRED')),
    parameters       JSONB NOT NULL DEFAULT '{}'::jsonb,
    provenance       JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_hash       VARCHAR(64),
    source_workpaper_hash VARCHAR(64),
    effective_from   DATE,
    effective_to     DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pack_id, revision)
);

CREATE TABLE compliance_pack_role (
    pack_id          VARCHAR(80) NOT NULL,
    pack_revision    INTEGER NOT NULL,
    role_id          VARCHAR(80) NOT NULL REFERENCES role_registry(role_id),
    required         BOOLEAN NOT NULL DEFAULT TRUE,
    sequence         INTEGER NOT NULL DEFAULT 0,
    document_type_id VARCHAR(80) REFERENCES document_type(document_type_id),
    acceptance_rule  JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_ref       JSONB,
    confirmed_by     VARCHAR(160),
    confirmed_at     TIMESTAMPTZ,
    PRIMARY KEY (pack_id, pack_revision, role_id),
    FOREIGN KEY (pack_id, pack_revision)
      REFERENCES compliance_pack(pack_id, revision)
);

CREATE TABLE compliance_rule (
    rule_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id          VARCHAR(80) NOT NULL,
    pack_revision    INTEGER NOT NULL,
    rule_code        VARCHAR(60) NOT NULL,
    attribute        VARCHAR(40) NOT NULL
                     CHECK (attribute IN ('completeness','correctness','accuracy','timeliness',
                                          'authorization_and_review')),
    primitive        VARCHAR(100) NOT NULL,
    arguments        JSONB NOT NULL DEFAULT '{}'::jsonb,
    dependencies     JSONB NOT NULL DEFAULT '{}'::jsonb,
    severity         VARCHAR(20) NOT NULL,
    on_fail          TEXT,
    sequence         INTEGER NOT NULL DEFAULT 0,
    source_ref       JSONB,
    active           BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (pack_id, pack_revision)
      REFERENCES compliance_pack(pack_id, revision),
    UNIQUE (pack_id, pack_revision, rule_code)
);

CREATE TABLE onboarding_model_snapshot (
    snapshot_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id          VARCHAR(80) NOT NULL,
    pack_revision    INTEGER NOT NULL,
    snapshot_json    JSONB NOT NULL,
    model_hash       VARCHAR(64) NOT NULL UNIQUE,
    approved_by      VARCHAR(160),
    approved_at      TIMESTAMPTZ,
    status            VARCHAR(20) NOT NULL DEFAULT 'DRAFT'
                      CHECK (status IN ('DRAFT','APPROVED','RETIRED')),
    FOREIGN KEY (pack_id, pack_revision)
      REFERENCES compliance_pack(pack_id, revision)
);

CREATE TABLE run (
    run_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id            VARCHAR(80) NOT NULL,
    pack_revision      INTEGER NOT NULL,
    run_type           VARCHAR(30) NOT NULL
                       CHECK (run_type IN ('ONBOARDING_REFERENCE','PERIOD_AUDIT','RETEST')),
    period_start       DATE,
    period_end         DATE,
    idempotency_key    VARCHAR(180) UNIQUE NOT NULL,
    status             VARCHAR(30) NOT NULL
                       CHECK (status IN ('QUEUED','COLLECTING','INCOMPLETE','READY','TESTING',
                                         'TESTED','REVIEWED','CLOSED')),
    evidence_complete  BOOLEAN NOT NULL DEFAULT FALSE,
    evidence_locked    BOOLEAN NOT NULL DEFAULT FALSE,
    overall_verdict    VARCHAR(20)
                       CHECK (overall_verdict IN ('PASS','FAIL','INDETERMINATE')),
    rules_version      VARCHAR(80) NOT NULL,
    model_hash         VARCHAR(64) NOT NULL,
    extractor_hash     VARCHAR(64),
    initiated_by       VARCHAR(160),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at         TIMESTAMPTZ,
    finished_at        TIMESTAMPTZ,
    FOREIGN KEY (pack_id, pack_revision)
      REFERENCES compliance_pack(pack_id, revision)
);

CREATE TABLE document (
    document_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                 UUID NOT NULL REFERENCES run(run_id),
    document_type_id       VARCHAR(80) REFERENCES document_type(document_type_id),
    role_id                VARCHAR(80) REFERENCES role_registry(role_id),
    filename               VARCHAR(320) NOT NULL,
    storage_uri            VARCHAR(1200) NOT NULL,
    sha256                 VARCHAR(64) NOT NULL,
    mime_type              VARCHAR(160) NOT NULL,
    classification_confidence NUMERIC(5,4),
    classification_status  VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    acceptance_status      VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    uploaded_by            VARCHAR(160),
    uploaded_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fact (
    fact_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_side        VARCHAR(10) NOT NULL
                         CHECK (evidence_side IN ('SIDE_A','SIDE_B')),
    entity_id            VARCHAR(80) REFERENCES company_master(entity_id),
    run_id               UUID REFERENCES run(run_id),
    document_id          UUID NOT NULL REFERENCES document(document_id),
    role_id              VARCHAR(80) REFERENCES role_registry(role_id),
    canonical_field_id   VARCHAR(80) NOT NULL REFERENCES canonical_field(canonical_field_id),
    row_index            INTEGER,
    value_text           TEXT,
    value_number         NUMERIC,
    value_date           DATE,
    value_boolean        BOOLEAN,
    valid_from           DATE,
    valid_to             DATE,
    confidence_score     NUMERIC(5,4) NOT NULL,
    extraction_method    VARCHAR(60) NOT NULL,
    extractor_hash       VARCHAR(64),
    model_version        VARCHAR(120),
    prompt_hash          VARCHAR(64),
    provenance            JSONB NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
      (evidence_side = 'SIDE_A' AND entity_id IS NOT NULL)
      OR
      (evidence_side = 'SIDE_B' AND run_id IS NOT NULL)
    )
);

CREATE TABLE step_result (
    result_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id         UUID NOT NULL REFERENCES run(run_id),
    rule_id        UUID NOT NULL REFERENCES compliance_rule(rule_id),
    verdict        VARCHAR(20) NOT NULL
                   CHECK (verdict IN ('PASS','FAIL','INDETERMINATE')),
    severity       VARCHAR(20) NOT NULL,
    actual_value   JSONB,
    expected_value JSONB,
    detail         TEXT,
    trace_tree     JSONB NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rule_comparison (
    comparison_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id      UUID NOT NULL REFERENCES step_result(result_id),
    left_fact_ids  JSONB NOT NULL DEFAULT '[]'::jsonb,
    right_fact_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_value JSONB,
    actual_value   JSONB,
    tolerance      JSONB,
    ok              BOOLEAN,
    detail          TEXT
);

CREATE TABLE onboarding_question (
    question_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id         VARCHAR(80) NOT NULL,
    pack_revision   INTEGER NOT NULL,
    question_kind   VARCHAR(50) NOT NULL,
    blocking        BOOLEAN NOT NULL DEFAULT TRUE,
    source_ref      JSONB NOT NULL,
    prompt          TEXT NOT NULL,
    options         JSONB NOT NULL DEFAULT '[]'::jsonb,
    interpretation  JSONB,
    answer          JSONB,
    rendered_readback TEXT,
    answered_by     VARCHAR(160),
    answered_at     TIMESTAMPTZ,
    confirmed_at    TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN','ASKED','INTERPRETED','CONFIRMED','BOUND','WITHDRAWN')),
    FOREIGN KEY (pack_id, pack_revision)
      REFERENCES compliance_pack(pack_id, revision)
);
```

## Schema simplification decisions

- `compliance_pack_role` includes the pack-specific required role and its confirmed document binding; a separate binding table is not required in the default design.
- `document_type_field` directly stores the canonical field mapping; a separate mapping table is not required initially.
- `run.run_type` separates reference/onboarding runs from real period audits without creating a second evidence pipeline.
- `onboarding_model_snapshot` provides a single immutable, hashable model artifact for replayability.
- `compliance_rule.arguments` and `dependencies` stay JSON because assertion structure is declarative and may evolve; normalize only if query requirements prove it necessary.

---

# 27. AI agents and tool contracts

There are two distinct conversational agents.

## 27.1 Admin Onboarding Agent

Purpose: guide first-time and change-time model creation.

### Tool set

```text
parse_workpaper(workpaper_id)
create_compliance_pack_draft(metadata)
list_existing_roles()
list_existing_document_types()
list_existing_canonical_fields()
propose_archetype(pack_id)
register_candidate_role(...)
register_candidate_document_type(...)
register_document_type_field(...)
propose_canonical_mapping(...)
compile_assertions(pack_id, workpaper_steps)
get_assertion_dependencies(pack_id)
propose_supporting_evidence_model(pack_id, reference_run_id)
derive_side_a_dependencies(pack_id)
create_onboarding_question(...)
confirm_onboarding_answer(question_id, typed_value)
validate_pack(pack_id, revision)
create_model_snapshot(pack_id, revision)
promote_pack(pack_id, revision)
```

### Tool safety

- tools expose typed parameters only;
- read tools may be called automatically;
- write tools require structured payloads;
- destructive actions require explicit confirmation;
- every write returns a provenance/event identifier;
- agent cannot call SQL directly.

## 27.2 BU Assistant

The BU assistant is deliberately less autonomous.

Allowed tools:

```text
get_obligation_requirements(pack_id, revision)
get_missing_evidence(run_id)
explain_document_requirement(run_id, role_id)
classify_uploaded_document(document_id)
get_evidence_status(run_id)
get_audit_status(run_id)
get_finding_explanation(result_id)
```

It should **not**:

- modify rules;
- modify document bindings;
- modify Side-A master;
- create new canonical fields;
- alter verdicts.

## 27.3 Agent output contract

Every agent response is split into:

```json
{
  "action": "PROPOSE|ASK|EXPLAIN|CONFIRM",
  "typed_payload": {},
  "source_refs": [],
  "confidence": "0.0000",
  "reason": "..."
}
```

The backend validates this object before it can affect state.

---

# 28. Technology stack and libraries

## 28.1 Recommended baseline

| Layer | Recommended technology |
|---|---|
| API | FastAPI |
| Validation | Pydantic |
| Database | PostgreSQL 15+ |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Workpaper parsing | openpyxl |
| PDF text / rendering | PyMuPDF |
| OCR baseline | Tesseract + PyMuPDF integration |
| OCR/layout candidate | PaddleOCR |
| Image processing | Pillow / OpenCV |
| DOCX | python-docx |
| LLM | approved enterprise LLM such as Gemini 2.5 Flash or equivalent |
| Agent framework | Prefer direct typed tool-calling; LangGraph only if durable state/branching is actually needed |
| Test framework | pytest |
| Arithmetic | `decimal.Decimal` |
| Object storage | S3-compatible immutable/WORM store where available |
| API auth | enterprise OIDC/OAuth2 |
| Observability | OpenTelemetry + approved backend |
| CI | enterprise CI/CD |

SQLAlchemy 2.x remains a reasonable ORM/data-access layer; its current 2.0 documentation describes ORM mappings,
relationships, sessions and querying as first-class capabilities. citeturn514786search0turn514786search5

openpyxl is appropriate for Excel 2010 OOXML workbooks and provides workbook/worksheet/cell APIs. citeturn514786search13

PyMuPDF is appropriate for fast PDF text extraction, page rendering and conditional OCR. citeturn784546search3turn784546search1

PaddleOCR is a strong candidate for complex OCR/document parsing workloads and its current documentation covers modern OCR pipelines and document parsing models. citeturn784546search2turn784546search6

## 28.2 Model versioning rule

Never store only a provider/model name. Persist:

```text
provider
model_name
model_version
prompt_hash
extractor_hash
schema_version
OCR engine + model version
```

## 28.3 LLM use cases

Appropriate:

- workpaper interpretation;
- reference-document semantic extraction;
- candidate document-type description;
- candidate field mapping;
- assertion proposal;
- natural-language explanation;
- onboarding question generation.

Not appropriate:

- final verdict;
- silent rule mutation;
- unconfirmed master updates;
- unregistered document binding;
- arbitrary Python execution.

---

# 29. Package / repository structure

```text
src/app/
├── main.py
├── config.py
├── api/
│   ├── admin.py
│   ├── bu.py
│   ├── onboarding.py
│   ├── evidence.py
│   └── audit.py
│
├── db/
│   ├── session.py
│   ├── models/
│   │   ├── archetype.py
│   │   ├── role.py
│   │   ├── canonical_field.py
│   │   ├── document_type.py
│   │   ├── compliance_pack.py
│   │   ├── compliance_rule.py
│   │   ├── run.py
│   │   ├── fact.py
│   │   └── result.py
│   └── repositories/
│
├── onboarding/
│   ├── chatbot.py
│   ├── workpaper_parser.py
│   ├── model_builder.py
│   ├── assertion_compiler.py
│   ├── dependency_resolver.py
│   ├── questions.py
│   └── promotion.py
│
├── registry/
│   ├── archetypes.py
│   ├── roles.py
│   ├── canonical_fields.py
│   ├── document_types.py
│   └── validator.py
│
├── ingestion/
│   ├── upload.py
│   ├── scanner.py
│   ├── mime.py
│   ├── hashes.py
│   └── storage.py
│
├── classification/
│   ├── classifier.py
│   ├── signals.py
│   ├── fusion.py
│   └── binding.py
│
├── extraction/
│   ├── dispatcher.py
│   ├── pdf.py
│   ├── spreadsheet.py
│   ├── docx.py
│   ├── ocr.py
│   ├── llm_extract.py
│   └── provenance.py
│
├── normalization/
│   ├── decimal.py
│   ├── dates.py
│   ├── strings.py
│   └── booleans.py
│
├── master/
│   ├── ingestion.py
│   ├── lifecycle.py
│   ├── projection.py
│   └── history.py
│
├── rules/
│   ├── compiler.py
│   ├── primitives.py
│   ├── validator.py
│   ├── dependencies.py
│   └── schemas.py
│
├── engines/
│   ├── base.py
│   ├── contract.py
│   ├── ast_eval.py
│   ├── calendar.py
│   └── optional/
│       ├── periodic_filing.py
│       ├── reconciliation.py
│       └── authorization.py
│
├── workflow/
│   ├── runs.py
│   ├── completeness.py
│   ├── evidence_lock.py
│   ├── audit.py
│   └── retest.py
│
├── reporting/
│   ├── findings.py
│   ├── trace.py
│   ├── working_paper.py
│   └── audit_report.py
│
├── agents/
│   ├── admin_agent.py
│   ├── bu_agent.py
│   ├── tools.py
│   ├── schemas.py
│   └── policies.py
│
└── web/
    ├── admin/
    ├── bu/
    ├── shared/
    └── templates/

migrations/
tests/
├── unit/
├── integration/
├── golden/
├── replay/
├── security/
└── fixtures/

docs/
├── architecture/
├── onboarding/
├── control-models/
└── runbooks/

config/
├── primitive_catalog.yaml
├── starter_canonical_fields.yaml
├── starter_roles.yaml
└── optional_archetypes.yaml

Dockerfile
docker-compose.yml
Makefile
pyproject.toml
poetry.lock / uv.lock
agent.manifest.json
README.md
```

---

# 30. API and service boundaries

## Admin APIs

```text
POST /admin/workpapers
GET  /admin/compliance-packs
POST /admin/compliance-packs/{id}/side-a/onboarding
POST /admin/compliance-packs/{id}/reference-documents
GET  /admin/onboarding/{id}/questions
POST /admin/onboarding/{id}/questions/{qid}/confirm
POST /admin/compliance-packs/{id}/promote
```

## BU APIs

```text
GET  /bu/obligations
POST /bu/runs
GET  /bu/runs/{run_id}/requirements
POST /bu/runs/{run_id}/documents
GET  /bu/runs/{run_id}/completeness
POST /bu/runs/{run_id}/lock
POST /bu/runs/{run_id}/audit
GET  /bu/runs/{run_id}/results
```

## Internal services

```text
WorkpaperCompiler
ReferenceModelBuilder
DocumentClassifier
RoleBinder
Extractor
CanonicalMapper
Normalizer
MasterLifecycleService
CompletenessService
AssertionEngine
AuditTraceService
ReportService
```

No external caller can invoke `AssertionEngine` with arbitrary rule text; it must use a stored active pack revision.

---

# 31. Auditability / MLOps / provenance

Every runtime audit should be reconstructible from durable IDs/hashes.

## Required run metadata

```text
run_id
pack_id
pack_revision
model_hash
rules_version
extractor_hash
classifier_version
OCR version
period
initiated_by
started_at
finished_at
```

## Fact provenance

Every AI-derived fact stores:

```text
source document
page / row / cell
bounding box if available
raw text
confidence
extraction method
model version
prompt hash
extractor hash
canonical field
```

## Configuration provenance

Every durable onboarding decision stores:

```text
source workpaper hash
source document hash
source page/cell
chat question id if applicable
candidate value
confirmed value
confirmed_by
confirmed_at
model revision
```

## Replay contract

A historical run must be replayable using:

```text
same pack revision
same model snapshot hash
same rule definitions
same fact IDs/values
same Side-A historical validity resolution
same calendar version
same primitive library version
```

Replaying must produce the same rule-comparison outcomes.

---

# 32. Security and determinism invariants

## Security

- tenant/entity isolation;
- role-based access control;
- object-storage encryption;
- immutable/WORM retention where mandated;
- malware scanning before parsing;
- SHA-256 file sealing;
- no raw chat-to-SQL path;
- no model-to-database direct writes;
- prompt injection treated as document content, never as system instruction;
- secrets in managed secret storage;
- least privilege for OCR/model/object-storage services.

## Determinism

- no floating-point arithmetic for financial calculations;
- explicit Decimal scale/rounding;
- explicit date parsing;
- versioned calendar;
- no wall clock inside rule evaluation;
- no network calls inside decision evaluation;
- no model call inside decision evaluation;
- immutable pack revisions;
- immutable audit results;
- `INDETERMINATE` rather than silent fallback on missing/invalid data.

---

# 33. Testing strategy

Testing must cover both **model creation** and **runtime audit**.

## 33.1 Unit tests

### Workpaper parser

- correct sheet detection;
- missing sheet;
- merged cells;
- blank cells;
- repeated attribute labels;
- parameter extraction;
- provenance cell coordinates.

### Assertion compiler

- each supported attribute;
- role dependency extraction;
- Side-A master dependency extraction;
- parameter dependency extraction;
- duplicate dependency elimination;
- conditional branch handling;
- malformed test step → blocking question.

### Document registry

- schema field creation;
- duplicate field detection;
- canonical mapping validation;
- field type mismatch.

### Classification

- known type;
- similar but wrong type;
- below confidence threshold;
- unregistered document type;
- multiple candidate types;
- conflicting signals.

### Normalization

- Indian number formats;
- Western number formats;
- negative parentheses;
- ambiguous dates;
- Unicode normalization;
- boolean unknown state.

### Rules

- allowed primitive;
- forbidden primitive;
- missing fact;
- wrong type;
- invalid expression;
- Decimal arithmetic;
- calendar roll-forward.

## 33.2 Integration tests

### Test A — first-time SOFTEX onboarding

```text
workpaper
→ pack
→ Side-A evidence
→ reference supporting docs
→ model proposal
→ Admin confirmation
→ ACTIVE pack
```

### Test B — new quarter

```text
ACTIVE SOFTEX model
→ new Side-A evidence
→ updated master
→ BU Q3 documents
→ completeness
→ audit
```

### Test C — wrong document

```text
Expected invoice
Uploaded bank realisation
→ document classified correctly
→ binding mismatch
→ invoice remains missing
→ audit blocked
```

### Test D — missing evidence

```text
one required role missing
→ evidence_complete = false
→ no audit call allowed
```

### Test E — conflicting Side-A master

```text
two certificates
same validity window
conflicting IEC
→ CONFLICT
→ Admin question
→ master not silently overwritten
```

## 33.3 Golden test sets

Maintain version-controlled golden documents:

```text
fixtures/golden/softex/
├── workpaper.xlsx
├── side_a/
│   ├── iec_certificate.pdf
│   ├── signatory_resolution.pdf
│   └── registration.pdf
├── reference_supporting/
│   ├── softex.pdf
│   ├── invoice.pdf
│   ├── acknowledgement.pdf
│   └── working_file.xlsx
└── expected_model.json
```

The golden model should contain:

```text
roles
accepted document types
canonical mappings
assertions
parameters
master dependencies
model hash
```

## 33.4 Replay tests

For every released pack revision:

```text
stored run
   ↓
replay using frozen model snapshot
   ↓
compare trace/result hashes
   ↓
must match exactly
```

## 33.5 Property-based tests

Use property-based testing for:

- Decimal reconciliation;
- date-window invariants;
- set equality;
- permutation-insensitive population comparisons;
- duplicate handling;
- validity-window transitions.

## 33.6 Mutation tests

Intentionally mutate:

- rule threshold;
- date offset;
- signatory;
- document role;
- invoice amount;
- canonical field;

and confirm the relevant test suite detects the change.

## 33.7 AI evaluation

Measure independently:

```text
classification accuracy
field extraction accuracy
role proposal accuracy
assertion proposal accuracy
canonical mapping accuracy
question-generation accuracy
hallucination rate
unsupported-document rate
```

AI quality is **not** a substitute for deterministic validation.

---

# 34. SOFTEX test walkthrough

This is the reference end-to-end scenario used to validate the architecture.

## 34.1 First-time Admin onboarding

Admin uploads `LLTC_70.xlsx`.

Application creates:

```text
compliance_pack:
  pack_id = LLTC_70
  status = DRAFT
```

Admin selects `LLTC_70` and uploads authoritative Side-A evidence.

System produces candidate entity facts such as:

```text
party.legal_name
party.iec
party.gstin
bank.ad_code
company_signatory
registration status
```

Admin uploads representative supporting documents from a prior period.

System proposes:

```text
filing_form      → softex_form
source_document  → commercial_invoice
acknowledgement  → stpi_ack
population_file  → softex_working_file
```

It then compiles assertions from the workpaper.

Admin confirms/corrects the model.

Result:

```text
SOFTEX MODEL v1 ACTIVE
```

## 34.2 Q3 Admin refresh

```text
Select SOFTEX
Upload updated signatory/registration evidence
→ Side-A master lifecycle
→ current master projection updated
```

No re-onboarding of SOFTEX rules is required unless the obligation changed.

## 34.3 Q3 BU run

BU selects:

```text
SOFTEX — Q3 FY2026
```

System displays the approved evidence checklist.

BU uploads:

```text
SOFTEX Form
Invoice
STPI Acknowledgement
SOFTEX Working File
```

System verifies all required roles.

If one document is the wrong type:

```text
Expected source_document
Detected ad_bank_realisation
→ role not satisfied
→ request invoice
→ audit blocked
```

Once complete:

```text
extract facts
→ normalize
→ compare Side-B to Side-A
→ execute assertions
→ produce trace
→ verdict
```

---

# 35. Quarterly reuse / replay

## Q1

```text
SOFTEX MODEL v1
    + Q1 Side-A state
    + Q1 Side-B facts
    → audit
```

## Q2

```text
SOFTEX MODEL v1
    + updated Side-A state
    + Q2 Side-B facts
    → audit
```

## Q3

```text
SOFTEX MODEL v1
    + current Side-A state
    + Q3 Side-B facts
    → audit
```

Only create `v2` when the **obligation/model changes**, such as:

- new workpaper assertion;
- changed statutory parameter;
- changed accepted evidence model;
- changed field semantics;
- confirmed document-type schema change;
- approved execution-contract change.

A new quarter by itself does not create a new pack revision.

---

# 36. Governance and change management

## 36.1 Immutable revisions

Never mutate an ACTIVE model in place.

```text
SOFTEX v1 ACTIVE
       ↓ amendment
SOFTEX v2 DRAFT
       ↓ review / shadow
SOFTEX v2 ACTIVE
       ↓
SOFTEX v1 RETIRED
```

## 36.2 Governance of global components

### Canonical field

Adding a field is a platform decision.

### Role

Adding a role is a platform/control-vocabulary decision.

### Document Type

A document type is registered from a real document/schema, not invented solely from prose.

### Assertion

Obligation-specific; governed by pack revision.

### Archetype

Optional and justified only by reusable execution semantics.

## 36.3 Promotion gate

A model can become ACTIVE only when:

```text
no blocking onboarding questions
AND
all assertions validate
AND
all required canonical fields exist
AND
all referenced document types are registered
AND
all role bindings are valid
AND
Side-A master dependencies are satisfiable
AND
reference model snapshot has a hash
AND
Admin approval is recorded
```

---

# 37. Implementation plan

## Phase 1 — Foundation

- PostgreSQL schema;
- SQLAlchemy models;
- Alembic migrations;
- object storage;
- authentication/RBAC;
- basic Admin/BU UI shells.

## Phase 2 — Workpaper / Pack onboarding

- openpyxl parser;
- Compliance Pack draft creation;
- onboarding chatbot;
- question/confirmation framework;
- model snapshotting.

## Phase 3 — Evidence registry

- document type registry;
- document type field registry;
- canonical field registry;
- role registry;
- document classification.

## Phase 4 — Reference-model learning

- reference supporting document ingestion;
- assertion compiler;
- evidence dependency resolver;
- candidate model builder;
- Admin confirmation workflow.

## Phase 5 — Side-A master

- entity evidence ingestion;
- validity-aware facts;
- ADD / RECONFIRM / SUPERSEDE / CONFLICT;
- master projection;
- historical lookups.

## Phase 6 — BU execution

- period run creation;
- evidence checklist;
- upload;
- classification;
- role binding;
- completeness gate;
- evidence lock.

## Phase 7 — Deterministic audit

- primitive catalogue;
- restricted evaluator;
- rule execution;
- trace tree;
- verdict rollup.

## Phase 8 — Production hardening

- MLOps metadata;
- WORM retention;
- threat model;
- load testing;
- replay tests;
- golden datasets;
- observability;
- DR/backup.

---

# 38. Definition of done

The platform is production-ready only when all of the following are true.

## Configuration

- workpaper upload creates a draft Compliance Pack;
- no Archetype selection is required to create an obligation;
- reference-model onboarding can use prior real evidence;
- Admin confirmations are auditable;
- every active pack has an immutable model snapshot hash.

## Evidence

- Side-A and Side-B are separate lifecycle classes;
- Side-A supports historical validity;
- Side-B is run/period scoped;
- document classification is governed;
- role binding is explicit;
- evidence completeness blocks audit when incomplete.

## Rules

- workpaper steps compile into structured assertions;
- assertions have typed dependencies;
- primitives are allow-listed;
- unsupported or unsafe expressions become INDETERMINATE.

## AI

- all agent tools are typed;
- no direct SQL from agents;
- model/prompt/OCR versions are recorded;
- AI never emits the final verdict;
- AI cannot silently mutate active configuration.

## Auditability

- every verdict traces to facts;
- every fact traces to documents;
- every document traces to a run;
- every run traces to a pack revision/model hash;
- every master lookup is time-aware;
- historical runs are replayable.

## Performance / reliability

- idempotent ingestion;
- duplicate file detection;
- safe retry semantics;
- bounded concurrency;
- OCR only when required;
- background processing for long-running extraction;
- failure isolation between documents.

---

# 39. Final architectural decisions

## 39.1 Primary model

```text
APPROVED OBLIGATION MODEL
     = Compliance Pack revision
       + linked registries
       + rules/assertions
       + evidence dependencies
       + model snapshot
```

This is the primary asset reused from quarter to quarter.

## 39.2 Archetype decision

**Archetypes are optional.**

Keep an Archetype only when it provides genuine shared execution semantics across many obligations.
Do not create one merely because obligations belong to a similar category.

## 39.3 Onboarding decision

First-time onboarding uses:

```text
workpaper
+ Side-A authoritative evidence
+ representative previous supporting documents
```

to construct the initial approved model.

## 39.4 Runtime decision

Future runs use:

```text
approved model
+ current Side-A state
+ new Side-B documents
```

No model rediscovery is needed unless the obligation configuration changes.

## 39.5 BU evidence decision

The BU does not manually define or negotiate requirements. The BU sees the evidence checklist generated from the **approved obligation model**.

## 39.6 No invented concrete document types

The system must not infer `commercial_invoice` merely because a workpaper contains the word “invoice”. A concrete type comes from a real registered sample/schema and is confirmed as part of the approved model.

## 39.7 Assertion-first evidence dependencies

The obligation's assertions are the reliable source for **what evidence roles are actually needed**. Concrete documents are resolved from the approved reference model.

## 39.8 Evidence completeness before audit

```text
COLLECT
  ↓
VALIDATE
  ↓
BIND
  ↓
COMPLETE?
  ├── NO → REQUEST MORE
  └── YES → LOCK → AUDIT
```

## 39.9 Final one-line architecture

> **Teach each obligation once from its real workpaper and representative evidence; approve a versioned reference model; refresh Side-A truth and ingest new Side-B evidence every period; then execute the same deterministic assertions against the new facts.**

---

# 40. Reference technology sources

The following official/current documentation was used to validate the technology recommendations in this version:

1. **PyMuPDF documentation** — PDF text extraction, rendering and OCR workflow.  
   https://pymupdf.readthedocs.io/en/latest/  
   https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html

2. **PaddleOCR documentation** — OCR and document parsing pipelines.  
   https://www.paddleocr.ai/main/en/

3. **openpyxl documentation** — Excel OOXML workbook parsing.  
   https://openpyxl.readthedocs.io/en/stable/

4. **SQLAlchemy 2.x documentation** — ORM, relationships and database access.  
   https://docs.sqlalchemy.org/en/20/orm/

These external references support library-selection statements only; the compliance model and architecture
remain governed by the requirements and decisions documented in this specification.

---

# Appendix A — Quick reference tables

## A.1 Who owns what?

| Concern | Owner |
|---|---|
| Obligation identity | Compliance Pack |
| Obligation-specific assertions | Compliance Pack / Rule registry |
| Representative onboarding | Admin chatbot |
| Side-A baseline | Company master + Side-A facts |
| Supporting evidence | BU run |
| Role vocabulary | Role registry |
| Document schema | Document Type / Document Type Field |
| Data vocabulary | Canonical Field |
| Atomic deterministic operation | Primitive catalogue |
| Shared control-family execution | Optional Archetype |
| Evidence completeness | Runtime workflow |
| Final verdict | Deterministic engine |

## A.2 Runtime decision chain

```text
SELECT OBLIGATION
      ↓
LOAD ACTIVE MODEL
      ↓
LOAD REQUIRED EVIDENCE DEPENDENCIES
      ↓
BU UPLOADS
      ↓
CLASSIFY
      ↓
ROLE BIND
      ↓
EVIDENCE COMPLETE?
      ↓ YES
LOCK
      ↓
EXTRACT
      ↓
NORMALIZE
      ↓
BUILD FACTS
      ↓
RESOLVE HISTORICAL SIDE-A MASTER
      ↓
EXECUTE ASSERTIONS
      ↓
STORE TRACE
      ↓
ROLLUP
      ↓
VERDICT
```

## A.3 First-time vs future quarter

| Activity | First time | Future quarter |
|---|---|---|
| Workpaper upload | Yes | Only if amended |
| Model construction | Yes | Reuse |
| Representative supporting docs | Yes | No |
| Admin confirmation | Yes | Only for changes/conflicts |
| Side-A evidence | Yes | Only changed/reconfirmed evidence |
| Side-A master refresh | Yes | As needed |
| BU supporting docs | Reference set | Every run |
| Assertion compilation | Yes | Reuse |
| Audit execution | After model approval | Every run |
| New run ID | Yes | Yes |
| New Side-B facts | Reference run + actual run | Yes |

---

# Appendix B — Example final SOFTEX model summary

```yaml
obligation:
  pack_id: LLTC_70
  name: SOFTEX Reporting
  revision: 1
  status: ACTIVE
  frequency: MONTHLY

model:
  archetype: periodic_filing@2.0.1   # optional platform contract

  required_roles:
    - filing_form
    - source_document
    - acknowledgement
    - population_file

  accepted_document_types:
    filing_form: softex_form
    source_document: commercial_invoice
    acknowledgement: stpi_ack
    population_file: softex_working_file

  assertions:
    - code: COR-01
      attribute: correctness
      primitive: matches_master
    - code: ACC-01
      attribute: accuracy
      primitive: value_equals
    - code: ACC-02
      attribute: accuracy
      primitive: sum_equals
    - code: TIM-01
      attribute: timeliness
      primitive: date_within_n_days
    - code: AUT-01
      attribute: authorization_and_review
      primitive: signature_valid
    - code: AUT-02
      attribute: authorization_and_review
      primitive: signer_authorized

  master_dependencies:
    - party.iec
    - party.legal_name
    - company_signatory
    - registration.status
```

The exact document types and bindings above are **examples of an approved model**, not defaults to be inferred from the phrase “invoice” alone.

---

# Appendix C — Non-goals

The platform is not intended to:

- let an LLM decide compliance;
- let BU define the compliance rule;
- infer unregistered document types at runtime;
- mutate active rules in place;
- treat all documents as Side A or all documents as Side B;
- overwrite historical master facts;
- create an Archetype for every new obligation;
- require Admin to understand the relational schema;
- make Admin manually encode 1,500 obligations into Python.

---

# Final statement

The system's scalability comes from **reuse of approved obligation models, registries, parsers, primitives,
and deterministic execution infrastructure**—not from forcing every obligation into the same template.

The first real occurrence of an obligation is where the platform learns and confirms the operational model.
Every later period is a controlled **data refresh + evidence collection + deterministic replay** of that approved model.

That is the intended production architecture.
