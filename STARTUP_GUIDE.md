# PVWood ERP — Fresh Start & Data Population Guide

How to bring up a **brand-new** PVWood ERP install and populate it with your
real factory data, in the right order. Start in **Warehouse** (build the
material catalogue + stock), then **Production Planning** (recipes, packing
specs, and finished-good BOMs).

> This guide is about **entering data through the app**. For installing the
> server itself (Python, Git, NSSM service, `.env`), see **`DEPLOY.md`**.

---

## 0. Why order matters (read this first)

Everything in the ERP is built on the **material catalogue**. Glue formulas,
packing specs, and finished-good BOMs all *reference* materials, so the
materials must exist first. The dependency chain:

```
   ┌─ WAREHOUSE ────────────────────────────────────────────┐
   │  1. Raw Materials  (boards, veneers, glue ingredients,  │
   │                     consumables, packing materials)     │
   │  2. Stock / Receiving (how much you hold)               │
   └────────────────────────────┬───────────────────────────┘
                                 │ (materials now exist)
   ┌─ PRODUCTION PLANNING ───────▼───────────────────────────┐
   │  3. Glue Formulas   (use glue-ingredient materials)     │
   │  4. Packing Specs   (use packing materials)             │
   │  5. Finished-Good SKUs + BOMs  (use boards, veneers,    │
   │        glue formulas, packing specs — needs 1,3,4 done) │
   └─────────────────────────────────────────────────────────┘
```

**Do not** try to build a finished-good BOM before its boards/veneers exist
(Warehouse step 1) and its glue formula + packing spec exist (Planning steps
3–4). The BOM Builder pickers will be empty otherwise.

---

## 1. First boot & login

On a fresh database the app auto-creates the schema and a **bootstrap admin**.

1. Start the server (`.\start.bat`, or the Windows service — see DEPLOY.md).
2. Open `http://<server>:<port>` (the port is whatever your `.env` sets;
   default `8000`).
3. Log in:
   - **Username:** `admin`
   - **Password:** `admin`
4. **Immediately change the password** — top-right user pill → My Profile.

> If `admin`/`admin` doesn't work, the database isn't fresh (someone already
> set it up) — use the real credentials, or see DEPLOY.md to reset.

---

## 2. Create the user accounts (as admin)

Sign in to the **Admin portal** (`/admin`) or the User Management page and
create one account per person, with the right role:

| Role | What they do here |
|---|---|
| **WAREHOUSE** | Raw Materials catalogue, Raw Material Receiving (stock), FG Warehouse |
| **PRODUCTION_PLANNING** | Bill of Materials (BOMs, Glue Formulas, Packing Specs), Finished Goods, orders |
| **DEPARTMENT_LEADER** | Station Hub logging on the production floor |
| **MANAGERIAL** | Everything + Factory Assistant + reports |

Create at least one **Warehouse** and one **Production Planning** user now —
they'll do the data entry in the next sections. Keep the `admin` account as a
managerial backup.

---

## 3. WAREHOUSE — build the material catalogue

**Log in as the Warehouse user.** Sidebar → **Raw Materials & Consumables**.

This is the foundation. Enter every material you buy, across all categories:

| Category | Examples | Used later by |
|---|---|---|
| **Boards** | MDF cores, plywood | FG BOM (base board) |
| **Veneers** | species/grades | FG BOM (face / back veneer) |
| **Glue & additives** | resin, latex, flour, pigments, hardener | Glue Formulas |
| **Consumables** | sandpaper, tape, etc. | Station consumable requests |
| **Packing** | cartons, pallets, strapping, labels | Packing Specs |
| **Others** | anything else | — |

### Option A — manual entry (small catalogues)
Use the **+ Add Material** button. Give each material a clear **code** and
name, set its **type/category**, unit, and reorder point.

### Option B — bulk CSV import (recommended for many items)
On the Raw Materials page open the **Data Tools** panel. Download the template
that matches what you're loading, fill it in Excel, and upload it:

- **Veneers** template — `…/api/upload/template/veneers`
- **Boards** template — `…/api/upload/template/boards`
- **Consumables** template — `…/api/upload/template/consumables`
- **General inventory** template — `…/api/upload/template/inventory`

(These download from the Data Tools panel buttons; you don't type the URLs.)
Keep the header row, one material per line, then upload the saved CSV.

> **Codes are permanent identifiers.** Glue formulas, packing specs, and BOMs
> match materials by code — pick a consistent scheme now (e.g. `BMCN2505`)
> and don't rename later.

---

## 4. WAREHOUSE — set opening stock

Once materials exist, record how much you currently hold so the ERP's
shortfall/replenishment logic is truthful.

- **Raw Material Receiving** (sidebar) — log incoming lots: supplier, lot
  reference, quantity, and (optionally) attach the supplier COA/cert PDF.
  This is also how supplier documents flow into Traceability later.
- **FC stock** (veneers/boards held at the factory floor) — the Raw Materials
  page has a **Bulk Upload FC Stock** tool under Data Tools
  (`…/api/upload/template/fc-stock`) if you want to seed those in bulk.

You can start with just current on-hand quantities; receiving with full lot +
document detail can begin as real deliveries arrive.

---

## 5. PRODUCTION PLANNING — recipes, specs, then BOMs

**Log in as the Production Planning user.** Sidebar → **Bill of Materials**.
The page has tabs across the top — work them **left-to-right in this order**:

### 5.1 Glue Formulas  *(tab: "Glue Formulas")*
Create each glue recipe by selecting its **ingredient materials** (the glue &
additives you entered in Warehouse step 3) and their proportions. Give each a
recipe code (e.g. `Glue 1`). A finished-good BOM will reference these by code.

### 5.2 Packing Specs  *(tab: "Packing Specs")*
Create a packing spec per packaging configuration, selecting the **packing
materials** (cartons/pallets/etc.) and quantities. Tie to a customer if the
packing differs per customer.

### 5.3 Finished-Good SKUs + BOMs  *(tab: "FG BOMs" → "New / Edit BOM")*
Now build each product. Click **New / Edit BOM** to open the **BOM Builder**:

1. **SKU code + name**, and dimensions (thickness / width / length) + Pcs per
   pallet.
2. **Base Board** — pick the board material; set Qty (sheets/pallet) and
   **Waste %** (boards are typically **0%**).
3. **Face Veneer** / **Back Veneer** — pick veneers; set Qty and **Waste %**
   (veneers vary — set the real figure per BOM; default 5%).
4. **Face Glue / Back Glue** — pick the **Glue Formula** (from 5.1) and usage
   per face.
5. **Packing** — attach the **Packing Spec** (from 5.2).
6. Save.

Repeat per product. These BOMs drive FC material requirements, shortfalls,
and costing.

> The **Finished Goods (FG)** page lists the SKUs you create here; you can
> review/edit product-level details there too.

---

## 6. Verify before going live

- **Raw Materials** page lists everything with sensible stock numbers.
- **Bill of Materials** → each product opens in the BOM Builder with its
  board, veneers, glue, and packing all populated (no empty pickers).
- Pick one finished good and check **FC Material Requirements** / **Material
  Shortfalls** compute against your stock (proves BOM ↔ materials linkage).
- Log in as each role and confirm they see the pages they need.

---

## 7. Suggested go-live sequence (recap)

1. **Boot + login** (`admin`/`admin` → change password).
2. **Create users** (at least Warehouse + Production Planning).
3. **Warehouse:** all raw materials (manual or CSV), then opening stock.
4. **Planning:** Glue Formulas → Packing Specs → Finished-Good BOMs.
5. **Verify** linkages, then start entering live sales orders / production.

Once this is in, day-to-day work (sales POs → production orders → station
logging → FG receiving) and the Factory Assistant / Traceability features all
have real data to operate on.
