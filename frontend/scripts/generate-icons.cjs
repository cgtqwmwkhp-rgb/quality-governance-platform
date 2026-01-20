/**
 * Generate PWA icons for the application
 * Run with: node scripts/generate-icons.cjs
 */

const fs = require('fs');
const path = require('path');

// Simple valid PNG (Electric Lime colored) - minimal 1x1 pixel
const createSimplePNG = () => {
  // This is a valid minimal PNG file with a green pixel
  return Buffer.from([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, // PNG signature
    0x00, 0x00, 0x00, 0x0D, // IHDR length
    0x49, 0x48, 0x44, 0x52, // IHDR
    0x00, 0x00, 0x00, 0x01, // width = 1
    0x00, 0x00, 0x00, 0x01, // height = 1
    0x08, // bit depth = 8
    0x02, // color type = RGB
    0x00, // compression
    0x00, // filter
    0x00, // interlace
    0x90, 0x77, 0x53, 0xDE, // IHDR CRC
    0x00, 0x00, 0x00, 0x0C, // IDAT length
    0x49, 0x44, 0x41, 0x54, // IDAT
    0x08, 0xD7, 0x63, 0x90, 0xB8, 0x2C, 0x05, 0x00, // compressed data
    0x02, 0x1E, 0x01, 0x1B, // CRC  
    0x00, 0x00, 0x00, 0x00, // IEND length
    0x49, 0x45, 0x4E, 0x44, // IEND
    0xAE, 0x42, 0x60, 0x82  // IEND CRC
  ]);
};

// Icon sizes needed
const sizes = [16, 32, 72, 96, 128, 144, 152, 192, 384, 512];

// Create icons directory
const iconsDir = path.join(__dirname, '../public/icons');
if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

// Generate each icon
sizes.forEach(size => {
  const filename = `icon-${size}x${size}.png`;
  const filepath = path.join(iconsDir, filename);
  fs.writeFileSync(filepath, createSimplePNG());
  console.log(`Created ${filename}`);
});

// Create shortcut icons
['shortcut-report.png', 'shortcut-sos.png', 'shortcut-track.png'].forEach(name => {
  const filepath = path.join(iconsDir, name);
  fs.writeFileSync(filepath, createSimplePNG());
  console.log(`Created ${name}`);
});

console.log('Done! Icons created in public/icons/');
