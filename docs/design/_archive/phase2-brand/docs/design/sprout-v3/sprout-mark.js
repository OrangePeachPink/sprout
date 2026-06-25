/*
 * sprout-mark.js — Sprout's living mark as a drop-in custom element.  v3.0.0-proposed
 *
 *   <script src="sprout-mark.js"></script>
 *   <sprout-mark band="moist"></sprout-mark>          <!-- mood derived from the calibrated band -->
 *   <sprout-mark mood="thirsty" size="96"></sprout-mark>
 *   <sprout-mark band="dry" static></sprout-mark>     <!-- force motion off -->
 *
 * Attributes:
 *   band   — one of: saturated | wet | moist | ideal | drying | dry | parched   (the UI band; or pass the
 *            firmware level: submerged | overwatered | "well watered" | ok | "needs water" | dry | "air-dry")
 *   mood   — one of: soaked | refreshed | thriving | content | thirsty | parched | faint   (overrides band)
 *   size   — pixel height of the mark (default 72)
 *   static — render the resting pose with no animation
 *
 * INVARIANT (ADR-0007 §5): mood follows the BAND, never the 0-100 index. The MOODS table below mirrors
 * mood-band-map.json (the canonical source) — keep them in sync. Honors prefers-reduced-motion.
 * Framework-agnostic; fits the ADR-0004 vanilla host. Use only where the brand boundary allows (ADR-0007 §6):
 * ambient / empty / loading / onboarding / notification / single-plant hero — NEVER inside dense numeric readouts.
 */
(function () {
  // band (UI + firmware aliases) -> mood key
  var BAND_TO_MOOD = {
    "saturated": "soaked", "submerged": "soaked",
    "wet": "refreshed", "overwatered": "refreshed",
    "moist": "thriving", "well watered": "thriving", "well-watered": "thriving",
    "ideal": "content", "ok": "content",
    "drying": "thirsty", "needs water": "thirsty", "needs-water": "thirsty",
    "dry": "parched",
    "parched": "faint", "air-dry": "faint", "air dry": "faint"
  };

  // mood -> rendering definition (mirrors mood-band-map.json)
  var MOODS = {
    soaked:    { motion: "breathe", variant: "upright",  c: { stem: "#0E7A86", sprout: "#34A853", leaf: "#0E7A86" }, droplet: true },
    refreshed: { motion: "breathe", variant: "upright",  c: { stem: "#0E7A86", sprout: "#8BD24F", leaf: "#17B6C4" } },
    thriving:  { motion: "breathe", variant: "thriving", c: { stem: "#2F7D3F", sprout: "#8BD24F", leaf: "#34A853", tip: "#A9DA6E" } },
    content:   { motion: "sway",    variant: "upright",  c: { stem: "#456B1F", sprout: "#A9DA6E", leaf: "#8BD24F" } },
    thirsty:   { motion: "droop",   variant: "droop",    c: { stem: "#B07D12", sprout: "#F5C97A", leaf: "#F5A623" } },
    parched:   { motion: "droop",   variant: "droop",    c: { stem: "#C2561F", sprout: "#F0A984", leaf: "#E8703A" } },
    faint:     { motion: "none",    variant: "droop",    c: { stem: "#B23B32", sprout: "#EAA39C", leaf: "#E0483D" } }
  };

  function svgFor(def) {
    var c = def.c;
    var leaves;
    if (def.variant === "droop") {
      leaves =
        '<path d="M12 26 C12 20 12 18 12 16"></path>' +
        '<path d="M12 16 C8 17 6 20 6 23 C10 22 12 19 12 16 Z" fill="' + c.sprout + '"></path>' +
        '<path d="M12 16 C16 17 18 20 18 23 C14 22 12 19 12 16 Z" fill="' + c.leaf + '"></path>';
    } else {
      var tip = def.variant === "thriving" && c.tip
        ? '<path d="M12 11 C9 6 11 3 12 1 C14 4 14 8 12 11 Z" fill="' + c.tip + '"></path>' : "";
      var droplet = def.droplet
        ? '<path d="M12 3 C12 3 14.4 5.6 12 7 C9.6 5.6 12 3 12 3 Z" fill="#17b6c4" stroke="' + c.stem + '"></path>' : "";
      leaves =
        droplet +
        '<path d="M12 26 V12"></path>' +
        '<path d="M12 13 C8 11 6 8 7 5 C11 6 12 10 12 13 Z" fill="' + c.sprout + '"></path>' +
        '<path d="M12 13 C16 11 18 8 17 5 C13 6 12 10 12 13 Z" fill="' + c.leaf + '"></path>' + tip;
    }
    // the leaves sit in a <g class="anim"> so motion animates the foliage; stem stays rooted
    return '<svg viewBox="0 0 24 28" fill="none" stroke="' + c.stem +
      '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" part="svg" width="100%" height="100%">' +
      '<g class="anim">' + leaves + '</g></svg>';
  }

  var KEYFRAMES =
    '@keyframes sm-sway{0%,100%{transform:rotate(-2.6deg)}50%{transform:rotate(2.6deg)}}' +
    '@keyframes sm-breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}' +
    '@keyframes sm-droop{0%,100%{transform:rotate(-1deg) translateY(0)}50%{transform:rotate(1.4deg) translateY(2px)}}';

  function motionCss(motion) {
    var origin = "transform-box:fill-box;transform-origin:50% 100%;";
    if (motion === "sway")    return ".anim{" + origin + "animation:sm-sway 6.5s ease-in-out infinite}";
    if (motion === "breathe") return ".anim{" + origin + "animation:sm-breathe 4.5s ease-in-out infinite}";
    if (motion === "droop")   return ".anim{" + origin + "animation:sm-droop 4.4s ease-in-out infinite}";
    return "";
  }

  var SproutMark = function () {};
  SproutMark = class extends HTMLElement {
    static get observedAttributes() { return ["band", "mood", "size", "static"]; }
    connectedCallback() { if (!this.shadowRoot) this.attachShadow({ mode: "open" }); this.render(); }
    attributeChangedCallback() { if (this.shadowRoot) this.render(); }

    resolveMood() {
      var m = (this.getAttribute("mood") || "").trim().toLowerCase();
      if (m && MOODS[m]) return m;
      var b = (this.getAttribute("band") || "").trim().toLowerCase();
      if (b && BAND_TO_MOOD[b]) return BAND_TO_MOOD[b];
      return "thriving";
    }

    render() {
      var mood = this.resolveMood();
      var def = MOODS[mood];
      var size = parseInt(this.getAttribute("size") || "72", 10);
      if (isNaN(size) || size <= 0) size = 72;
      var noMotion = this.hasAttribute("static");
      var anim = noMotion ? "" : motionCss(def.motion);
      this.setAttribute("role", "img");
      this.setAttribute("aria-label", "Sprout — " + mood);
      this.shadowRoot.innerHTML =
        "<style>" +
          ":host{display:inline-block;line-height:0;width:" + Math.round(size * 24 / 28) + "px;height:" + size + "px}" +
          KEYFRAMES + anim +
          "@media (prefers-reduced-motion: reduce){.anim{animation:none!important}}" +
        "</style>" + svgFor(def);
    }
  };

  if (!customElements.get("sprout-mark")) customElements.define("sprout-mark", SproutMark);
})();
