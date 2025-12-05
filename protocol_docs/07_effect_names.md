# Symphony Effect Names Reference

This document provides a complete listing of effect names extracted from the Zengge Android app
resources (`com.zengge.blev2.apk` v1.5.0). These names correspond to the effect IDs used in
Symphony Mode commands.

**Source**: Extracted from Android APK `res/values/strings.xml` using `apktool`. All effect names
are from the official Zengge app strings, not reverse-engineered guesses.

## Effect Types Overview

The Zengge app defines three categories of Symphony effects:

| Type | ID Range | Count | Java Source | Description |
|------|----------|-------|-------------|-------------|
| Scene Effects | 1-44 | 44 | `dd/i.java` method `f()` | Basic animations with color configuration UI |
| Build Effects | 100-399 (UI), 1-300 (internal) | 300 | `dd/i.java` method `i()` | Complex pre-defined animations |
| Settled Mode Effects | 1-10 | 10 | `ge/s1.java` - `ge/r1.java` | Simple static effects |

**Note on Build Effect IDs**: The Java code adds 99 to internal IDs for UI display, so
Build Effect #1 appears as ID 100 in the UI, #2 as 101, etc.

---

## Scene Effects (IDs 1-44)

Scene effects are basic animations that allow user customization of colors. The Java code
in `dd/i.java` method `f()` associates each effect with a `SymphonyEffectUIType` that determines
which color pickers are shown in the app.

### UI Types

- **UIType_StartColor_EndColor**: Two color pickers for gradient/transition
- **UIType_Only_ForegroundColor**: Single foreground color picker
- **UIType_ForegroundColor_BackgroundColor**: Two pickers for foreground and background
- **UIType_FirstColor_SecondColor**: Two alternating colors
- **UIType_Only_BackgroundColor**: Single background color picker
- **IType_NoColor**: No color customization (uses preset colors)

### Scene Effect List

| ID | Effect Name | UI Type |
|----|-------------|---------|
| 1 | Change gradually | StartColor_EndColor |
| 2 | Bright up and Fade gradually | Only_ForegroundColor |
| 3 | Change quickly | StartColor_EndColor |
| 4 | Strobe-flash | StartColor_EndColor |
| 5 | Running, 1point from start to end | ForegroundColor_BackgroundColor |
| 6 | Running, 1point from end to start | ForegroundColor_BackgroundColor |
| 7 | Running, 1point from the middle to the both ends | ForegroundColor_BackgroundColor |
| 8 | Running, 1point from the both ends to the middle | ForegroundColor_BackgroundColor |
| 9 | Overlay, from start to end | ForegroundColor_BackgroundColor |
| 10 | Overlay, from end to start | ForegroundColor_BackgroundColor |
| 11 | Overlay, from the middle to the both ends | ForegroundColor_BackgroundColor |
| 12 | Overlay, from the both ends to the middle | ForegroundColor_BackgroundColor |
| 13 | Fading and running, 1point from start to end | ForegroundColor_BackgroundColor |
| 14 | Fading and running, 1point from end to start | ForegroundColor_BackgroundColor |
| 15 | Olivary Flowing, from start to end | ForegroundColor_BackgroundColor |
| 16 | Olivary Flowing, from end to start | ForegroundColor_BackgroundColor |
| 17 | Running, 1point w/background from start to end | ForegroundColor_BackgroundColor |
| 18 | Running, 1point w/background from end to start | ForegroundColor_BackgroundColor |
| 19 | 2 colors run, multi points w/black background from start to end | FirstColor_SecondColor |
| 20 | 2 colors run, multi points w/black background from end to start | FirstColor_SecondColor |
| 21 | 2 colors run alternately, fading from start to end | FirstColor_SecondColor |
| 22 | 2 colors run alternately, fading from end to start | FirstColor_SecondColor |
| 23 | 2 colors run alternately, multi points from start to end | FirstColor_SecondColor |
| 24 | 2 colors run alternately, multi points from end to start | FirstColor_SecondColor |
| 25 | Fading out Flows, from start to end | FirstColor_SecondColor |
| 26 | Fading out Flows, from end to start | FirstColor_SecondColor |
| 27 | 7 colors run alternately, 1 point with multi points background, from start to end | Only_BackgroundColor |
| 28 | 7 colors run alternately, 1 point with multi points background, from end to start | Only_BackgroundColor |
| 29 | 7 colors run alternately, 1 point from start to end | NoColor |
| 30 | 7 colors run alternately, 1 point from end to start | NoColor |
| 31 | 7 colors run alternately, multi points from start to end | NoColor |
| 32 | 7 colors run alternately, multi points from end to start | NoColor |
| 33 | 7 colors overlay, multi points from start to end | NoColor |
| 34 | 7 colors overlay, multi points from end to start | NoColor |
| 35 | 7 colors overlay, multi points from the middle to the both ends | NoColor |
| 36 | 7 colors overlay, multi points from the both ends to the middle | NoColor |
| 37 | 7 colors flow gradually, from start to end | NoColor |
| 38 | 7 colors flow gradually, from end to start | NoColor |
| 39 | Fading out run, 7 colors from start to end | NoColor |
| 40 | Fading out run, 7 colors from end to start | NoColor |
| 41 | Runs in olivary, 7 colors from start to end | NoColor |
| 42 | Runs in olivary, 7 colors from end to start | NoColor |
| 43 | Fading out run, 7 colors start with white color from start to end | NoColor |
| 44 | Fading out run, 7 colors start with white color from end to start | NoColor |

---

## Build Effects (IDs 1-300, UI shows 100-399)

Build effects are complex pre-defined animations. These load from string resources named
`symphony_SymphonyBuild_1` through `symphony_SymphonyBuild_300`.

### Build Effect List

| ID | UI ID | Effect Name |
|----|-------|-------------|
| 1 | 100 | Circulate all modes |
| 2 | 101 | 7 colors change gradually |
| 3 | 102 | 7 colors run in olivary |
| 4 | 103 | 7 colors change quickly |
| 5 | 104 | 7 colors strobe-flash |
| 6 | 105 | 7 colors running, 1 point from start to end and return back |
| 7 | 106 | 7 colors running, multi points from start to end and return back |
| 8 | 107 | 7 colors overlay, multi points from start to end and return back |
| 9 | 108 | 7 colors overlay, multi points from the middle to the both ends and return back |
| 10 | 109 | 7 colors flow gradually, from start to end and return back |
| 11 | 110 | Fading out run, 7 colors from start to end and return back |
| 12 | 111 | Runs in olivary, 7 colors from start to end and return back |
| 13 | 112 | Fading out run, 7 colors start with white color from start to end and return back |
| 14 | 113 | Run circularly, 7 colors with black background, 1point from start to end |
| 15 | 114 | Run circularly, 7 colors with red background, 1point from start to end |
| 16 | 115 | Run circularly, 7 colors with green background, 1point from start to end |
| 17 | 116 | Run circularly, 7 colors with blue background, 1point from start to end |
| 18 | 117 | Run circularly, 7 colors with yellow background, 1point from start to end |
| 19 | 118 | Run circularly, 7 colors with purple background, 1point from start to end |
| 20 | 119 | Run circularly, 7 colors with cyan background, 1point from start to end |
| 21 | 120 | Run circularly, 7 colors with white background, 1point from start to end |
| 22 | 121 | Run circularly, 7 colors with black background, 1point from end to start |
| 23 | 122 | Run circularly, 7 colors with red background, 1point from end to start |
| 24 | 123 | Run circularly, 7 colors with green background, 1point from end to start |
| 25 | 124 | Run circularly, 7 colors with blue background, 1point from end to start |
| 26 | 125 | Run circularly, 7 colors with yellow background, 1point from end to start |
| 27 | 126 | Run circularly, 7 colors with purple background, 1point from end to start |
| 28 | 127 | Run circularly, 7 colors with cyan background, 1point from end to start |
| 29 | 128 | Run circularly, 7 colors with white background, 1point from end to start |
| 30 | 129 | Run circularly, 7 colors with black background, 1point from start to end and return back |
| 31 | 130 | Run circularly, 7 colors with red background, 1point from start to end and return back |
| 32 | 131 | Run circularly, 7 colors with green background, 1point from start to end and return back |
| 33 | 132 | Run circularly, 7 colors with blue background, 1point from start to end and return back |
| 34 | 133 | Run circularly, 7 colors with yellow background, 1point from start to end and return back |
| 35 | 134 | Run circularly, 7 colors with purple background, 1point from start to end and return back |
| 36 | 135 | Run circularly, 7 colors with cyan background, 1point from start to end and return back |
| 37 | 136 | Run circularly, 7 colors with white background, 1point from start to end and return back |
| 38 | 137 | Run circularly, 7 colors with black background, 1point from middle to both ends |
| 39 | 138 | Run circularly, 7 colors with red background, 1point from middle to both ends |
| 40 | 139 | Run circularly, 7 colors with green background, 1point from middle to both ends |
| 41 | 140 | Run circularly, 7 colors with blue background, 1point from middle to both ends |
| 42 | 141 | Run circularly, 7 colors with yellow background, 1point from middle to both ends |
| 43 | 142 | Run circularly, 7 colors with purple background, 1point from middle to both ends |
| 44 | 143 | Run circularly, 7 colors with cyan background, 1point from middle to both ends |
| 45 | 144 | Run circularly, 7 colors with white background, 1point from middle to both ends |
| 46 | 145 | Run circularly, 7 colors with black background, 1point from both ends to middle |
| 47 | 146 | Run circularly, 7 colors with red background, 1point from both ends to middle |
| 48 | 147 | Run circularly, 7 colors with green background, 1point from both ends to middle |
| 49 | 148 | Run circularly, 7 colors with blue background, 1point from both ends to middle |
| 50 | 149 | Run circularly, 7 colors with yellow background, 1point from both ends to middle |
| 51 | 150 | Run circularly, 7 colors with purple background, 1point from both ends to middle |
| 52 | 151 | Run circularly, 7 colors with cyan background, 1point from both ends to middle |
| 53 | 152 | Run circularly, 7 colors with white background, 1point from both ends to middle |
| 54 | 153 | Run circularly, 7 colors with black background, 1point from middle to both ends and return back |
| 55 | 154 | Run circularly, 7 colors with red background, 1point from middle to both ends and return back |
| 56 | 155 | Run circularly, 7 colors with green background, 1point from middle to both ends and return back |
| 57 | 156 | Run circularly, 7 colors with blue background, 1point from middle to both ends and return back |
| 58 | 157 | Run circularly, 7 colors with yellow background, 1point from middle to both ends and return back |
| 59 | 158 | Run circularly, 7 colors with purple background, 1point from middle to both ends and return back |
| 60 | 159 | Run circularly, 7 colors with cyan background, 1point from middle to both ends and return back |
| 61 | 160 | Run circularly, 7 colors with white background, 1point from middle to both ends and return back |
| 62 | 161 | Overlay circularly, 7 colors with black background from start to end |
| 63 | 162 | Overlay circularly, 7 colors with red background from start to end |
| 64 | 163 | Overlay circularly, 7 colors with green background from start to end |
| 65 | 164 | Overlay circularly, 7 colors with blue background from start to end |
| 66 | 165 | Overlay circularly, 7 colors with yellow background from start to end |
| 67 | 166 | Overlay circularly, 7 colors with purple background from start to end |
| 68 | 167 | Overlay circularly, 7 colors with cyan background from start to end |
| 69 | 168 | Overlay circularly, 7 colors with white background from start to end |
| 70 | 169 | Overlay circularly, 7 colors with black background from end to start |
| 71 | 170 | Overlay circularly, 7 colors with red background from end to start |
| 72 | 171 | Overlay circularly, 7 colors with green background from end to start |
| 73 | 172 | Overlay circularly, 7 colors with blue background from end to start |
| 74 | 173 | Overlay circularly, 7 colors with yellow background from end to start |
| 75 | 174 | Overlay circularly, 7 colors with purple background from end to start |
| 76 | 175 | Overlay circularly, 7 colors with cyan background from end to start |
| 77 | 176 | Overlay circularly, 7 colors with white background from end to start |
| 78 | 177 | Overlay circularly, 7 colors with black background from start to end and return back |
| 79 | 178 | Overlay circularly, 7 colors with red background from start to end and return back |
| 80 | 179 | Overlay circularly, 7 colors with green background from start to end and return back |
| 81 | 180 | Overlay circularly, 7 colors with blue background from start to end and return back |
| 82 | 181 | Overlay circularly, 7 colors with yellow background from start to end and return back |
| 83 | 182 | Overlay circularly, 7 colors with purple background from start to end and return back |
| 84 | 183 | Overlay circularly, 7 colors with cyan background from start to end and return back |
| 85 | 184 | Overlay circularly, 7 colors with white background from start to end and return back |
| 86 | 185 | Overlay circularly, 7 colors with black background from middle to both sides |
| 87 | 186 | Overlay circularly, 7 colors with red background from middle to both sides |
| 88 | 187 | Overlay circularly, 7 colors with green background from middle to both sides |
| 89 | 188 | Overlay circularly, 7 colors with blue background from middle to both sides |
| 90 | 189 | Overlay circularly, 7 colors with yellow background from middle to both sides |
| 91 | 190 | Overlay circularly, 7 colors with purple background from middle to both sides |
| 92 | 191 | Overlay circularly, 7 colors with cyan background from middle to both sides |
| 93 | 192 | Overlay circularly, 7 colors with white background from middle to both sides |
| 94 | 193 | Overlay circularly, 7 colors with black background from both ends to middle |
| 95 | 194 | Overlay circularly, 7 colors with red background from both ends to middle |
| 96 | 195 | Overlay circularly, 7 colors with green background from both ends to middle |
| 97 | 196 | Overlay circularly, 7 colors with blue background from both ends to middle |
| 98 | 197 | Overlay circularly, 7 colors with yellow background from both ends to middle |
| 99 | 198 | Overlay circularly, 7 colors with purple background from both ends to middle |
| 100 | 199 | Overlay circularly, 7 colors with cyan background from both ends to middle |
| 101 | 200 | Overlay circularly, 7 colors with white background from both ends to middle |
| 102 | 201 | Overlay circularly, 7 colors with black background from middle to both sides and return back |
| 103 | 202 | Overlay circularly, 7 colors with red background from middle to both sides and return back |
| 104 | 203 | Overlay circularly, 7 colors with green background from middle to both sides and return back |
| 105 | 204 | Overlay circularly, 7 colors with blue background from middle to both sides and return back |
| 106 | 205 | Overlay circularly, 7 colors with yellow background from middle to both sides and return back |
| 107 | 206 | Overlay circularly, 7 colors with purple background from middle to both sides and return back |
| 108 | 207 | Overlay circularly, 7 colors with cyan background from middle to both sides and return back |
| 109 | 208 | Overlay circularly, 7 colors with white background from middle to both sides and return back |
| 110 | 209 | Fading out run circularly, 1point with black background from start to end |
| 111 | 210 | Fading out run circularly, 1point with red background from start to end |
| 112 | 211 | Fading out run circularly, 1point with green background from start to end |
| 113 | 212 | Fading out run circularly, 1point with blue background from start to end |
| 114 | 213 | Fading out run circularly, 1point with yellow background from start to end |
| 115 | 214 | Fading out run circularly, 1point with purple background from start to end |
| 116 | 215 | Fading out run circularly, 1point with cyan background from start to end |
| 117 | 216 | Fading out run circularly, 1point with white background from start to end |
| 118 | 217 | Fading out run circularly, 1point with black background from end to start |
| 119 | 218 | Fading out run circularly, 1point with red background from end to start |
| 120 | 219 | Fading out run circularly, 1point with green background from end to start |
| 121 | 220 | Fading out run circularly, 1point with blue background from end to start |
| 122 | 221 | Fading out run circularly, 1point with yellow background from end to start |
| 123 | 222 | Fading out run circularly, 1point with purple background from end to start |
| 124 | 223 | Fading out run circularly, 1point with cyan background from end to start |
| 125 | 224 | Fading out run circularly, 1point with white background from end to start |
| 126 | 225 | Fading out run circularly, 1point with black background from start to end and return back |
| 127 | 226 | Fading out run circularly, 1point with red background from start to end and return back |
| 128 | 227 | Fading out run circularly, 1point with green background from start to end and return back |
| 129 | 228 | Fading out run circularly, 1point with blue background from start to end and return back |
| 130 | 229 | Fading out run circularly, 1point with yellow background from start to end and return back |
| 131 | 230 | Fading out run circularly, 1point with purple background from start to end and return back |
| 132 | 231 | Fading out run circularly, 1point with cyan background from start to end and return back |
| 133 | 232 | Fading out run circularly, 1point with white background from start to end and return back |
| 134 | 233 | Flows in olivary circularly, 7 colors with black background from start to end |
| 135 | 234 | Flows in olivary circularly, 7 colors with red background from start to end |
| 136 | 235 | Flows in olivary circularly, 7 colors with green background from start to end |
| 137 | 236 | Flows in olivary circularly, 7 colors with blue background from start to end |
| 138 | 237 | Flows in olivary circularly, 7 colors with yellow background from start to end |
| 139 | 238 | Flows in olivary circularly, 7 colors with purple background from start to end |
| 140 | 239 | Flows in olivary circularly, 7 colors with cyan background from start to end |
| 141 | 240 | Flows in olivary circularly, 7 colors with white background from start to end |
| 142 | 241 | Flows in olivary circularly, 7 colors with black background from end to start |
| 143 | 242 | Flows in olivary circularly, 7 colors with red background from end to start |
| 144 | 243 | Flows in olivary circularly, 7 colors with green background from end to start |
| 145 | 244 | Flows in olivary circularly, 7 colors with blue background from end to start |
| 146 | 245 | Flows in olivary circularly, 7 colors with yellow background from end to start |
| 147 | 246 | Flows in olivary circularly, 7 colors with purple background from end to start |
| 148 | 247 | Flows in olivary circularly, 7 colors with cyan background from end to start |
| 149 | 248 | Flows in olivary circularly, 7 colors with white background from end to start |
| 150 | 249 | Flows in olivary circularly, 7 colors with black background from start to end and return back |
| 151 | 250 | Flows in olivary circularly, 7 colors with red background from start to end and return back |
| 152 | 251 | Flows in olivary circularly, 7 colors with green background from start to end and return back |
| 153 | 252 | Flows in olivary circularly, 7 colors with blue background from start to end and return back |
| 154 | 253 | Flows in olivary circularly, 7 colors with yellow background from start to end and return back |
| 155 | 254 | Flows in olivary circularly, 7 colors with purple background from start to end and return back |
| 156 | 255 | Flows in olivary circularly, 7 colors with cyan background from start to end and return back |
| 157 | 256 | Flows in olivary circularly, 7 colors with white background from start to end and return back |
| 158 | 257 | Fading out run circularly, 7 colors each in black fading from start to end |
| 159 | 258 | Fading out run circularly, 7 colors each in red fading from start to end |
| 160 | 259 | Fading out run circularly, 7 colors each in green fading from start to end |
| 161 | 260 | Fading out run circularly, 7 colors each in blue fading from start to end |
| 162 | 261 | Fading out run circularly, 7 colors each in yellow fading from start to end |
| 163 | 262 | Fading out run circularly, 7 colors each in purple fading from start to end |
| 164 | 263 | Fading out run circularly, 7 colors each in cyan fading from start to end |
| 165 | 264 | Fading out run circularly, 7 colors each in white fading from start to end |
| 166 | 265 | Fading out run circularly, 7 colors each in black fading from end to start |
| 167 | 266 | Fading out run circularly, 7 colors each in red fading from end to start |
| 168 | 267 | Fading out run circularly, 7 colors each in green fading from end to start |
| 169 | 268 | Fading out run circularly, 7 colors each in blue fading from end to start |
| 170 | 269 | Fading out run circularly, 7 colors each in yellow fading from end to start |
| 171 | 270 | Fading out run circularly, 7 colors each in purple fading from end to start |
| 172 | 271 | Fading out run circularly, 7 colors each in cyan fading from end to start |
| 173 | 272 | Fading out run circularly, 7 colors each in white fading from end to start |
| 174 | 273 | Fading out run circularly, 7 colors each in black fading from start to end and return back |
| 175 | 274 | Fading out run circularly, 7 colors each in red fading from start to end and return back |
| 176 | 275 | Fading out run circularly, 7 colors each in green fading from start to end and return back |
| 177 | 276 | Fading out run circularly, 7 colors each in blue fading from start to end and return back |
| 178 | 277 | Fading out run circularly, 7 colors each in yellow fading from start to end and return back |
| 179 | 278 | Fading out run circularly, 7 colors each in purple fading from start to end and return back |
| 180 | 279 | Fading out run circularly, 7 colors each in cyan fading from start to end and return back |
| 181 | 280 | Fading out run circularly, 7 colors each in white fading from start to end and return back |
| 182 | 281 | 7 colors run circularly, each color in every 1 point with black background from start to end |
| 183 | 282 | 7 colors run circularly, each color in every 1 point with red background from start to end |
| 184 | 283 | 7 colors run circularly, each color in every 1 point with green background from start to end |
| 185 | 284 | 7 colors run circularly, each color in every 1 point with blue background from start to end |
| 186 | 285 | 7 colors run circularly, each color in every 1 point with yellow background from start to end |
| 187 | 286 | 7 colors run circularly, each color in every 1 point with purple background from start to end |
| 188 | 287 | 7 colors run circularly, each color in every 1 point with cyan background from start to end |
| 189 | 288 | 7 colors run circularly, each color in every 1 point with white background from start to end |
| 190 | 289 | 7 colors run circularly, each color in every 1 point with black background from end to start |
| 191 | 290 | 7 colors run circularly, each color in every 1 point with red background from end to start |
| 192 | 291 | 7 colors run circularly, each color in every 1 point with green background from end to start |
| 193 | 292 | 7 colors run circularly, each color in every 1 point with blue background from end to start |
| 194 | 293 | 7 colors run circularly, each color in every 1 point with yellow background from end to start |
| 195 | 294 | 7 colors run circularly, each color in every 1 point with purple background from end to start |
| 196 | 295 | 7 colors run circularly, each color in every 1 point with cyan background from end to start |
| 197 | 296 | 7 colors run circularly, each color in every 1 point with white background from end to start |
| 198 | 297 | 7 colors run circularly, each color in every 1 point with black background from start to end and return back |
| 199 | 298 | 7 colors run circularly, each color in every 1 point with red background from start to end and return back |
| 200 | 299 | 7 colors run circularly, each color in every 1 point with green background from start to end and return back |
| 201 | 300 | 7 colors run circularly, each color in every 1 point with blue background from start to end and return back |
| 202 | 301 | 7 colors run circularly, each color in every 1 point with yellow background from start to end and return back |
| 203 | 302 | 7 colors run circularly, each color in every 1 point with purple background from start to end and return back |
| 204 | 303 | 7 colors run circularly, each color in every 1 point with cyan background from start to end and return back |
| 205 | 304 | 7 colors run circularly, each color in every 1 point with white background from start to end and return back |
| 206 | 305 | 7 colors run circularly, each color in multi points with black background from start to end |
| 207 | 306 | 7 colors run circularly, each color in multi points with red background from start to end |
| 208 | 307 | 7 colors run circularly, each color in multi points with green background from start to end |
| 209 | 308 | 7 colors run circularly, each color in multi points with blue background from start to end |
| 210 | 309 | 7 colors run circularly, each color in multi points with yellow background from start to end |
| 211 | 310 | 7 colors run circularly, each color in multi points with purple background from start to end |
| 212 | 311 | 7 colors run circularly, each color in multi points with cyan background from start to end |
| 213 | 312 | 7 colors run circularly, each color in multi points with white background from start to end |
| 214 | 313 | 7 colors run circularly, each color in multi points with black background from end to start |
| 215 | 314 | 7 colors run circularly, each color in multi points with red background from end to start |
| 216 | 315 | 7 colors run circularly, each color in multi points with green background from end to start |
| 217 | 316 | 7 colors run circularly, each color in multi points with blue background from end to start |
| 218 | 317 | 7 colors run circularly, each color in multi points with yellow background from end to start |
| 219 | 318 | 7 colors run circularly, each color in multi points with purple background from end to start |
| 220 | 319 | 7 colors run circularly, each color in multi points with cyan background from end to start |
| 221 | 320 | 7 colors run circularly, each color in multi points with white background from end to start |
| 222 | 321 | 7 colors run circularly, each color in multi points with black background from start to end and return back |
| 223 | 322 | 7 colors run circularly, each color in multi points with red background from start to end and return back |
| 224 | 323 | 7 colors run circularly, each color in multi points with green background from start to end and return back |
| 225 | 324 | 7 colors run circularly, each color in multi points with blue background from start to end and return back |
| 226 | 325 | 7 colors run circularly, each color in multi points with yellow background from start to end and return back |
| 227 | 326 | 7 colors run circularly, each color in multi points with purple background from start to end and return back |
| 228 | 327 | 7 colors run circularly, each color in multi points with cyan background from start to end and return back |
| 229 | 328 | 7 colors run circularly, each color in multi points with white background from start to end and return back |
| 230 | 329 | 7 colors each in black run circularly, multi points from start to end |
| 231 | 330 | 7 colors each in red run circularly, multi points from start to end |
| 232 | 331 | 7 colors each in green run circularly, multi points from start to end |
| 233 | 332 | 7 colors each in blue run circularly, multi points from start to end |
| 234 | 333 | 7 colors each in yellow run circularly, multi points from start to end |
| 235 | 334 | 7 colors each in purple run circularly, multi points from start to end |
| 236 | 335 | 7 colors each in cyan run circularly, multi points from start to end |
| 237 | 336 | 7 colors each in white run circularly, multi points from start to end |
| 238 | 337 | 7 colors each in black run circularly, multi points from end to start |
| 239 | 338 | 7 colors each in red run circularly, multi points from end to start |
| 240 | 339 | 7 colors each in green run circularly, multi points from end to start |
| 241 | 340 | 7 colors each in blue run circularly, multi points from end to start |
| 242 | 341 | 7 colors each in yellow run circularly, multi points from end to start |
| 243 | 342 | 7 colors each in purple run circularly, multi points from end to start |
| 244 | 343 | 7 colors each in cyan run circularly, multi points from end to start |
| 245 | 344 | 7 colors each in white run circularly, multi points from end to start |
| 246 | 345 | 7 colors each in black run circularly, multi points from start to end and return back |
| 247 | 346 | 7 colors each in red run circularly, multi points from start to end and return back |
| 248 | 347 | 7 colors each in green run circularly, multi points from start to end and return back |
| 249 | 348 | 7 colors each in cyan run circularly, multi points from start to end and return back |
| 250 | 349 | 7 colors each in yellow run circularly, multi points from start to end and return back |
| 251 | 350 | 7 colors each in purple run circularly, multi points from start to end and return back |
| 252 | 351 | 7 colors each in blue run circularly, multi points from start to end and return back |
| 253 | 352 | 7 colors each in white run circularly, multi points from start to end and return back |
| 254 | 353 | Flows gradually and circularly, 6 colors with black background from start to end |
| 255 | 354 | Flows gradually and circularly, 6 colors with red background from start to end |
| 256 | 355 | Flows gradually and circularly, 6 colors with green background from start to end |
| 257 | 356 | Flows gradually and circularly, 6 colors with blue background from start to end |
| 258 | 357 | Flows gradually and circularly, 6 colors with yellow background from start to end |
| 259 | 358 | Flows gradually and circularly, 6 colors with purple background from start to end |
| 260 | 359 | Flows gradually and circularly, 6 colors with cyan background from start to end |
| 261 | 360 | Flows gradually and circularly, 6 colors with white background from start to end |
| 262 | 361 | Flows gradually and circularly, 6 colors with red background from end to start |
| 263 | 362 | Flows gradually and circularly, 6 colors with green background from end to start |
| 264 | 363 | Flows gradually and circularly, 6 colors with blue background from end to start |
| 265 | 364 | Flows gradually and circularly, 6 colors with yellow background from end to start |
| 266 | 365 | Flows gradually and circularly, 6 colors with purple background from end to start |
| 267 | 366 | Flows gradually and circularly, 6 colors with cyan background from end to start |
| 268 | 367 | Flows gradually and circularly, 6 colors with white background from end to start |
| 269 | 368 | Flows gradually and circularly, 6 colors with red background from start to end and return back |
| 270 | 369 | Flows gradually and circularly, 6 colors with green background from start to end and return back |
| 271 | 370 | Flows gradually and circularly, 6 colors with blue background from start to end and return back |
| 272 | 371 | Flows gradually and circularly, 6 colors with yellow background from start to end and return back |
| 273 | 372 | Flows gradually and circularly, 6 colors with purple background from start to end and return back |
| 274 | 373 | Flows gradually and circularly, 6 colors with cyan background from start to end and return back |
| 275 | 374 | Flows gradually and circularly, 6 colors with white background from start to end and return back |
| 276 | 375 | 7 colors run with black background from start to end |
| 277 | 376 | 7 colors run with red background from start to end |
| 278 | 377 | 7 colors run with green background from start to end |
| 279 | 378 | 7 colors run with blue background from start to end |
| 280 | 379 | 7 colors run with yellow background from start to end |
| 281 | 380 | 7 colors run with purple background from start to end |
| 282 | 381 | 7 colors run with cyan background from start to end |
| 283 | 382 | 7 colors run with white background from start to end |
| 284 | 383 | 7 colors run with black background from end to start |
| 285 | 384 | 7 colors run with red background from end to start |
| 286 | 385 | 7 colors run with green background from end to start |
| 287 | 386 | 7 colors run with blue background from end to start |
| 288 | 387 | 7 colors run with yellow background from end to start |
| 289 | 388 | 7 colors run with purple background from end to start |
| 290 | 389 | 7 colors run with cyan background from end to start |
| 291 | 390 | 7 colors run with white background from end to start |
| 292 | 391 | 7 colors run with black background from start to end and return back |
| 293 | 392 | 7 colors run with red background from start to end and return back |
| 294 | 393 | 7 colors run with green background from start to end and return back |
| 295 | 394 | 7 colors run with blue background from start to end and return back |
| 296 | 395 | 7 colors run with yellow background from start to end and return back |
| 297 | 396 | 7 colors run with purple background from start to end and return back |
| 298 | 397 | 7 colors run with cyan background from start to end and return back |
| 299 | 398 | 7 colors run with white background from start to end and return back |
| 300 | 399 | 7 colors run gradually + 7 colors run in olivary |

---

## Combination Effects (Build IDs 290-300)

The last 11 Build effects are combinations of basic patterns:

| ID | UI ID | Effect Name |
|----|-------|-------------|
| 290 | 389 | 7 colors run gradually + 7 colors run in olivary |
| 291 | 390 | 7 colors run gradually + 7 colors change quickly |
| 292 | 391 | 7 colors run gradually + 7 colors flash |
| 293 | 392 | 7 colors run in olivary + 7 colors change quickly |
| 294 | 393 | 7 colors run in olivary + 7 colors flash |
| 295 | 394 | 7 colors change quickly + 7 colors flash |
| 296 | 395 | 7 colors run gradually + 7 colors run in olivary + 7 colors change quickly |
| 297 | 396 | 7 colors run gradually + 7 colors run in olivary + 7 colors flash |
| 298 | 397 | 7 colors run gradually + 7 colors change quickly + 7 colors flash |
| 299 | 398 | 7 colors run in olivary + 7 colors change quickly + 7 colors flash |
| 300 | 399 | 7 colors run gradually + 7 colors run in olivary + 7 colors change quickly + 7 color flash |

---

## Effect Pattern Categories

Analyzing the effect names reveals systematic patterns:

### Direction Patterns

- **from start to end**: Animation flows left to right (or beginning to end of LED strip)
- **from end to start**: Animation flows right to left
- **from middle to both ends**: Animation expands from center
- **from both ends to middle**: Animation contracts to center
- **and return back**: Animation reverses direction after completing

### Animation Types

- **Change gradually**: Smooth color transitions
- **Change quickly**: Abrupt color changes
- **Strobe-flash**: Rapid on/off flashing
- **Running**: Point(s) moving along strip
- **Overlay**: Colors layering/stacking
- **Fading**: Colors fade in/out
- **Flows in olivary**: Flowing wave pattern
- **Circularly**: Continuous loop

### Color Patterns

- **7 colors**: Uses rainbow spectrum (Red, Orange, Yellow, Green, Cyan, Blue, Purple)
- **6 colors**: Rainbow minus one color
- **2 colors**: Alternating pair of colors
- **with [color] background**: Solid background color behind animation

### Point Patterns

- **1point**: Single LED moves
- **multi points**: Multiple LEDs move together
- **each color in every 1 point**: Each LED shows different color
- **each color in multi points**: Groups of LEDs show same color

---

## Java Source References

The effect names are loaded from Android string resources by the following Java code:

**Scene Effects** (`dd/i.java` method `f()`):

```java
// IDs 1-44 from symphony_SymphonyEffect1 through symphony_SymphonyEffect44
e(1, appO.getString(2131821815), SymphonyEffectUIType.UIType_StartColor_EndColor);
// ... continues through ID 44
```

**Build Effects** (`dd/i.java` method `i()`):

```java
// IDs 1-300 from symphony_SymphonyBuild_1 through symphony_SymphonyBuild_300
for (int i10 = 1; i10 <= 300; i10++) {
    arrayList.add(new ListValueItem(
        i10 + 99,  // UI ID = internal ID + 99
        String.valueOf(i10) + ". " + context.getString(
            context.getResources().getIdentifier(
                "symphony_SymphonyBuild_" + String.valueOf(i10),
                "string",
                context.getPackageName()
            )
        )
    ));
}
```

---

## Notes

1. **"Olivary"** appears to be a translation quirk - likely means "olive-shaped" or wave-like pattern
2. **Build Effect ID 1 "Circulate all modes"** cycles through all other effects automatically
3. Effect availability varies by device model and firmware version
4. Some effects may require specific LED chip types (WS2812B, etc.) to display correctly
