# Nutflix Platform Vision & Business Strategy

> This document captures the business model, product strategy, and ecosystem concepts for Nutflix.  
> For technical architecture and development phases, see `Nutflix_Vision_Document.md`.

---

## 1. The Ecosystem Concept

### Nutflix = The Platform
The branded experience, website, and app where wildlife videos can be shared, viewed, liked, commented on, and followed.

- Users subscribe to see live feeds from around the world
- Favorite individual squirrels and follow their activity
- Discover new SquirrelBoxes globally
- Like, comment, and engage with content

### Nutwork = The Network
The underlying distributed collection of all shared SquirrelBoxes.

- Conceptually, users who share to Nutflix make their box part of the Nutwork
- Think of it as the infrastructure layer beneath the consumer platform
- Marketing hook: **"Your SquirrelBox joins the Nutwork when you share!"**

---

## 2. Business Model

### The "OnlyFans for Squirrels" Angle

Turn potential brand confusion into memorable viral differentiation.

**Creator Economy Model:**
- NutPod owners become "creators" by sharing their feeds
- Revenue sharing for popular feeds
- Creators build followings around their local wildlife

**Subscription Tiers:**

| Tier | Price | Access |
|------|-------|--------|
| **Creator (Free)** | $0/mo | Share your feed publicly → get free premium access |
| **Viewer** | $X/mo | Access all public feeds globally, no sharing required |
| **Premium** | $X/mo | HD streams, historical archives, AI highlights, priority support |

**Key Insight:** Sharing your feed = free subscription. This incentivizes network growth while rewarding contributors.

---

## 3. Hardware Product Line

### Current Products

| Product | Description |
|---------|-------------|
| **NutPod** | Squirrel-focused observation device (SquirrelBox + NutNode) |
| **NutNode** | Main electronics module — Raspberry Pi 5, dual cameras, sensors. Reused across all device types. |
| **SquirrelBox** | Premium wood enclosure with plexiglass viewing window |
| **Solar Battery Box (SBB)** | Off-grid power system (1S4P 21700 Li-ion, MPPT charging) |

### Future Variants (Planned)

| Product | Concept |
|---------|---------|
| **ScoutPod** | Lightweight/portable variant for scouting locations |
| **GroundPod** | Ground-level variant for different wildlife |
| **BirdBox** | Species-specific variant for bird watching |

### Hardware Philosophy
- Modular and upgradeable
- Premium materials (real wood, quality components)
- Weather-resistant design
- Easy installation for non-technical users

---

## 4. Hardware Engineering Roadmap

The current generation of NutNode electronics runs on stock Raspberry Pi 5 retail boards inside a custom SquirrelBox enclosure. This is the right answer for early product iteration — stock parts, full community support, every line of code in the project runs without modification. It constrains us in three ways though: the form factor wastes real estate on connectors and IO we don't use, the onboard WiFi antenna is internal and limited in range (a real problem for deployment in tree-mounted enclosures across a backyard), and the per-unit BOM cost is higher than it needs to be at scale.

### v2: Pi Compute Module 5 + custom carrier board

The next hardware iteration is the Raspberry Pi Compute Module 5 (CM5) on a custom carrier board designed specifically for the NutPod. The CM5 uses the same SoC and software stack as the Pi 5 — meaning every line of code currently in the project runs unchanged — but strips the board to just the chip plus RAM and optional eMMC, exposed via a 100-pin edge connector.

The carrier board then exposes only the IO we actually use:
- Two CSI camera ports
- I2C for the BME280 environmental sensor
- GPIO for the IR emitters
- USB-A for future expansion (microphone, secondary storage)
- Power input compatible with both wall and Solar Battery Box

The headline feature is the **U.FL antenna connector on the CM5 itself.** Pairing it with an SMA pigtail and a small external antenna mounted on the SquirrelBox exterior solves the marginal-WiFi problem that is currently the biggest practical limitation of outdoor deployment. Realistic WiFi range improves from "edge of the home network" to "comfortable across walls and yards."

Per-unit BOM also drops meaningfully: CM5 starts around $45 (4GB, no eMMC) vs ~$80 for a Pi 5 retail board, and the carrier board strips out USB hubs, HDMI controllers, the SD card slot, and other components the sealed product doesn't need.

### Speculative: fully custom electronics

A fully custom PCB with a non-Pi SoC would give total hardware control, but it requires months of electrical engineering work, risks losing compatibility with the Linux + Picamera2 stack that the entire project depends on, and offers no clear functional advantage over the CM5 path for this product. **Not a current consideration.** Possible only if NutPod ever reaches production volumes where the per-unit BOM savings justify the multi-month engineering investment.

### Triggering conditions for hardware redesign

Hardware redesign should not begin before:

- Phase 4 (AI classification) is at least underway and the inference workload's CPU/RAM requirements are known.
- Multiple NutPods have been deployed outdoors for long enough to surface real-world learnings: enclosure thermals, IR illumination reach, BME280 placement, antenna gain requirements, weatherproofing failures.
- A clear product-line decision has been made — i.e., NutPod has moved from "personal project" to "product I plan to sell."

Going to custom hardware too early locks design decisions in before we know which ones matter. The Pi 5 retail board is the right development platform; the CM5 is the right production platform; the time to switch is when product-market learnings are in.

---

## 5. Attract Pack Strategy

### The Problem
New users don't know how to attract squirrels to their SquirrelBox. Empty boxes = no footage = unhappy customers.

### The Solution: Nutflix Attract Packs

**Starter Pack (Bundled with Purchase)**
- Large dried nut blend:
  - Black oil sunflower seeds
  - Peanuts in-shell
  - Corn kernels
- Instructions for scattering around SquirrelBox
- Works even if box is elevated

**Single-Use Refill Packs**
- Premium nut blend
- Dried fruit mix
- Peanut butter sample (squirrel crack)
- Seasonal varieties

### Marketing Copy
> "Bring them running! Our Nutflix Attract Packs are squirrel-approved treats designed to get you incredible footage fast. Thoughtfully designed to make onboarding easy."

### Business Rationale
- ✅ Reduces buyer confusion about feeding
- ✅ Increases successful first visits
- ✅ Creates happy customers who see results quickly
- ✅ High-margin consumable revenue stream
- ✅ Recurring purchase opportunity

---

## 6. Customer Education Philosophy

### Key Messages

**Feeding is Essential**
> No consistent feeding = no consistent footage

**Wildlife Takes Time**
- Squirrels need to discover and trust the SquirrelBox
- First visit might take days or weeks
- Consistency is key

**Success Strategy**
> "Fast-track their trust with daily visits and consistent feeding."

### Honest Expectations
- Be upfront about acclimation time
- Educate on natural squirrel behavior
- Emphasize humane, wildlife-friendly design
- Support through user manual, marketing copy, FAQ

### Design Philosophy
- Multiple exits (squirrels feel safe)
- Chew-friendly surfaces (natural behavior)
- Covered feeding area (weather protection)
- Comfortable size (not cramped)

---

## 7. Platform Features Roadmap

### Phase 1: Local Only
- Personal monitoring dashboard
- Local clip storage
- No sharing, no network

### Phase 2: Optional Sharing
- Opt-in to share clips publicly
- Basic discovery feed
- Simple profiles

### Phase 3: Creator Economy
- Follower counts
- Revenue sharing program
- Creator analytics
- Featured feeds

### Phase 4: Full Platform
- Live streaming
- AI-curated highlight reels
- Squirrel identification/tracking
- Global leaderboards
- Community features
- Mobile apps

---

## 8. Marketing & Positioning

### Taglines (Brainstorm)
- "OnlyFans, but for squirrels"
- "Your backyard, streaming worldwide"
- "Join the Nutwork"
- "Premium squirrel entertainment"
- "Where wildlife meets WiFi"

### Target Audience
- Nature enthusiasts
- Backyard wildlife watchers
- Makers/tinkerers (early adopters)
- Families with kids
- Remote workers wanting ambient nature content
- Content creators looking for unique niche

### Competitive Differentiation
- Not just a camera—a platform
- Creator economy model
- Premium hardware quality
- Community/social features
- AI-powered content curation

---

## 9. Revenue Streams

1. **Hardware Sales** - NutPod, SquirrelBox, Solar Battery Box
2. **Subscriptions** - Viewer and Premium tiers
3. **Consumables** - Attract Packs and refills
4. **Accessories** - Mounts, cables, spare parts
5. **Revenue Share** - Platform cut of creator earnings (future)

---

## 10. Long-Term Vision

Nutflix starts with squirrels but the model scales to:
- Bird watching
- Backyard wildlife of all kinds
- Nature education
- Citizen science contributions
- Wildlife research partnerships

The core insight: **People want to connect with nature, share what they see, and be part of a community doing the same.**

---

## Document History

| Date | Changes |
|------|---------|
| 2025-01-15 | Initial creation from architecture brainstorming sessions |
| 2026-05-08 | Aligned product table with technical doc (NutPod = device, NutNode = electronics module). Fixed cross-reference filename. |
| 2026-05-17 | Added Section 4 (Hardware Engineering Roadmap) documenting the CM5 + custom carrier board path as the v2 hardware direction. Notes external U.FL antenna as the headline feature solving the current marginal-WiFi limitation. Full custom PCB explicitly deferred. Subsequent sections renumbered. |

---

*This document is for business/product planning. For technical implementation, see the Nutflix Vision Document.*
