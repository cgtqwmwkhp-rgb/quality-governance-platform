import { useState } from 'react';
import { RotateCcw, X } from 'lucide-react';

// Injury types with colors
const INJURY_TYPES = [
  { id: 'cut', label: 'Cut / Laceration', color: '#ef4444', icon: '🩸' },
  { id: 'bruise', label: 'Bruise / Contusion', color: '#8b5cf6', icon: '💜' },
  { id: 'burn', label: 'Burn', color: '#f97316', icon: '🔥' },
  { id: 'fracture', label: 'Fracture / Break', color: '#eab308', icon: '🦴' },
  { id: 'sprain', label: 'Sprain / Strain', color: '#22c55e', icon: '💪' },
  { id: 'crush', label: 'Crush Injury', color: '#ec4899', icon: '⚠️' },
  { id: 'puncture', label: 'Puncture Wound', color: '#06b6d4', icon: '📌' },
  { id: 'other', label: 'Other', color: '#6b7280', icon: '❓' },
];

// Body regions for front and back
const BODY_REGIONS = {
  front: [
    { id: 'head-front', label: 'Head (Front)', path: 'M150,20 C180,20 200,45 200,75 C200,105 180,125 150,125 C120,125 100,105 100,75 C100,45 120,20 150,20 Z', cx: 150, cy: 70 },
    { id: 'face', label: 'Face', path: 'M130,50 L170,50 L175,90 L125,90 Z', cx: 150, cy: 70 },
    { id: 'neck-front', label: 'Neck (Front)', path: 'M135,125 L165,125 L165,150 L135,150 Z', cx: 150, cy: 137 },
    { id: 'chest', label: 'Chest', path: 'M100,150 L200,150 L210,250 L90,250 Z', cx: 150, cy: 200 },
    { id: 'abdomen', label: 'Abdomen', path: 'M90,250 L210,250 L200,320 L100,320 Z', cx: 150, cy: 285 },
    { id: 'groin', label: 'Groin / Hip', path: 'M100,320 L200,320 L190,360 L110,360 Z', cx: 150, cy: 340 },
    { id: 'left-shoulder', label: 'Left Shoulder', path: 'M60,150 L100,150 L100,180 L60,170 Z', cx: 80, cy: 165 },
    { id: 'right-shoulder', label: 'Right Shoulder', path: 'M200,150 L240,150 L240,170 L200,180 Z', cx: 220, cy: 165 },
    { id: 'left-upper-arm', label: 'Left Upper Arm', path: 'M45,170 L75,180 L75,250 L45,250 Z', cx: 60, cy: 210 },
    { id: 'right-upper-arm', label: 'Right Upper Arm', path: 'M225,180 L255,170 L255,250 L225,250 Z', cx: 240, cy: 210 },
    { id: 'left-elbow', label: 'Left Elbow', path: 'M40,250 L75,250 L75,280 L40,280 Z', cx: 57, cy: 265 },
    { id: 'right-elbow', label: 'Right Elbow', path: 'M225,250 L260,250 L260,280 L225,280 Z', cx: 242, cy: 265 },
    { id: 'left-forearm', label: 'Left Forearm', path: 'M35,280 L70,280 L65,360 L30,360 Z', cx: 50, cy: 320 },
    { id: 'right-forearm', label: 'Right Forearm', path: 'M230,280 L265,280 L270,360 L235,360 Z', cx: 250, cy: 320 },
    { id: 'left-hand', label: 'Left Hand', path: 'M20,360 L65,360 L60,410 L15,410 Z', cx: 40, cy: 385 },
    { id: 'right-hand', label: 'Right Hand', path: 'M235,360 L280,360 L285,410 L240,410 Z', cx: 260, cy: 385 },
    { id: 'left-thigh', label: 'Left Thigh', path: 'M110,360 L150,360 L145,470 L105,470 Z', cx: 127, cy: 415 },
    { id: 'right-thigh', label: 'Right Thigh', path: 'M150,360 L190,360 L195,470 L155,470 Z', cx: 172, cy: 415 },
    { id: 'left-knee', label: 'Left Knee', path: 'M105,470 L145,470 L145,510 L105,510 Z', cx: 125, cy: 490 },
    { id: 'right-knee', label: 'Right Knee', path: 'M155,470 L195,470 L195,510 L155,510 Z', cx: 175, cy: 490 },
    { id: 'left-shin', label: 'Left Shin', path: 'M105,510 L140,510 L135,620 L100,620 Z', cx: 120, cy: 565 },
    { id: 'right-shin', label: 'Right Shin', path: 'M160,510 L195,510 L200,620 L165,620 Z', cx: 180, cy: 565 },
    { id: 'left-foot', label: 'Left Foot', path: 'M90,620 L140,620 L145,670 L85,670 Z', cx: 115, cy: 645 },
    { id: 'right-foot', label: 'Right Foot', path: 'M160,620 L210,620 L215,670 L155,670 Z', cx: 185, cy: 645 },
  ],
  back: [
    { id: 'head-back', label: 'Head (Back)', path: 'M150,20 C180,20 200,45 200,75 C200,105 180,125 150,125 C120,125 100,105 100,75 C100,45 120,20 150,20 Z', cx: 150, cy: 70 },
    { id: 'neck-back', label: 'Neck (Back)', path: 'M135,125 L165,125 L165,150 L135,150 Z', cx: 150, cy: 137 },
    { id: 'upper-back', label: 'Upper Back', path: 'M100,150 L200,150 L210,220 L90,220 Z', cx: 150, cy: 185 },
    { id: 'mid-back', label: 'Mid Back (Spine)', path: 'M120,220 L180,220 L180,280 L120,280 Z', cx: 150, cy: 250 },
    { id: 'lower-back', label: 'Lower Back', path: 'M100,280 L200,280 L200,340 L100,340 Z', cx: 150, cy: 310 },
    { id: 'buttocks', label: 'Buttocks', path: 'M100,340 L200,340 L190,380 L110,380 Z', cx: 150, cy: 360 },
    { id: 'left-shoulder-back', label: 'Left Shoulder (Back)', path: 'M60,150 L100,150 L100,180 L60,170 Z', cx: 80, cy: 165 },
    { id: 'right-shoulder-back', label: 'Right Shoulder (Back)', path: 'M200,150 L240,150 L240,170 L200,180 Z', cx: 220, cy: 165 },
    { id: 'left-tricep', label: 'Left Tricep', path: 'M45,170 L75,180 L75,250 L45,250 Z', cx: 60, cy: 210 },
    { id: 'right-tricep', label: 'Right Tricep', path: 'M225,180 L255,170 L255,250 L225,250 Z', cx: 240, cy: 210 },
    { id: 'left-elbow-back', label: 'Left Elbow (Back)', path: 'M40,250 L75,250 L75,280 L40,280 Z', cx: 57, cy: 265 },
    { id: 'right-elbow-back', label: 'Right Elbow (Back)', path: 'M225,250 L260,250 L260,280 L225,280 Z', cx: 242, cy: 265 },
    { id: 'left-forearm-back', label: 'Left Forearm (Back)', path: 'M35,280 L70,280 L65,360 L30,360 Z', cx: 50, cy: 320 },
    { id: 'right-forearm-back', label: 'Right Forearm (Back)', path: 'M230,280 L265,280 L270,360 L235,360 Z', cx: 250, cy: 320 },
    { id: 'left-hand-back', label: 'Left Hand (Back)', path: 'M20,360 L65,360 L60,410 L15,410 Z', cx: 40, cy: 385 },
    { id: 'right-hand-back', label: 'Right Hand (Back)', path: 'M235,360 L280,360 L285,410 L240,410 Z', cx: 260, cy: 385 },
    { id: 'left-hamstring', label: 'Left Hamstring', path: 'M110,380 L150,380 L145,470 L105,470 Z', cx: 127, cy: 425 },
    { id: 'right-hamstring', label: 'Right Hamstring', path: 'M150,380 L190,380 L195,470 L155,470 Z', cx: 172, cy: 425 },
    { id: 'left-knee-back', label: 'Left Knee (Back)', path: 'M105,470 L145,470 L145,510 L105,510 Z', cx: 125, cy: 490 },
    { id: 'right-knee-back', label: 'Right Knee (Back)', path: 'M155,470 L195,470 L195,510 L155,510 Z', cx: 175, cy: 490 },
    { id: 'left-calf', label: 'Left Calf', path: 'M105,510 L140,510 L135,620 L100,620 Z', cx: 120, cy: 565 },
    { id: 'right-calf', label: 'Right Calf', path: 'M160,510 L195,510 L200,620 L165,620 Z', cx: 180, cy: 565 },
    { id: 'left-heel', label: 'Left Heel', path: 'M90,620 L140,620 L145,670 L85,670 Z', cx: 115, cy: 645 },
    { id: 'right-heel', label: 'Right Heel', path: 'M160,620 L210,620 L215,670 L155,670 Z', cx: 185, cy: 645 },
  ],
};

export interface InjurySelection {
  regionId: string;
  regionLabel: string;
  injuryType: string;
  injuryLabel: string;
  view: 'front' | 'back';
}

interface BodyInjurySelectorProps {
  injuries: InjurySelection[];
  onChange: (injuries: InjurySelection[]) => void;
}

export default function BodyInjurySelector({ injuries, onChange }: BodyInjurySelectorProps) {
  const [view, setView] = useState<'front' | 'back'>('front');
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [showInjuryTypes, setShowInjuryTypes] = useState(false);

  const currentRegions = BODY_REGIONS[view];
  
  const handleRegionClick = (regionId: string) => {
    setSelectedRegion(regionId);
    setShowInjuryTypes(true);
  };

  const handleInjuryTypeSelect = (injuryTypeId: string) => {
    if (!selectedRegion) return;
    
    const region = currentRegions.find(r => r.id === selectedRegion);
    const injuryType = INJURY_TYPES.find(t => t.id === injuryTypeId);
    
    if (!region || !injuryType) return;

    const newInjury: InjurySelection = {
      regionId: selectedRegion,
      regionLabel: region.label,
      injuryType: injuryTypeId,
      injuryLabel: injuryType.label,
      view,
    };

    // Remove existing injury for this region if any
    const filtered = injuries.filter(i => i.regionId !== selectedRegion);
    onChange([...filtered, newInjury]);
    
    setShowInjuryTypes(false);
    setSelectedRegion(null);
  };

  const removeInjury = (regionId: string) => {
    onChange(injuries.filter(i => i.regionId !== regionId));
  };

  const getRegionColor = (regionId: string) => {
    const injury = injuries.find(i => i.regionId === regionId);
    if (injury) {
      const type = INJURY_TYPES.find(t => t.id === injury.injuryType);
      return type?.color || '#ef4444';
    }
    return 'transparent';
  };

  const isRegionSelected = (regionId: string) => {
    return injuries.some(i => i.regionId === regionId) || selectedRegion === regionId;
  };

  return (
    <div className="space-y-4">
      {/* View Toggle */}
      <div className="flex items-center justify-center gap-2 bg-white/5 rounded-xl p-1">
        <button
          type="button"
          onClick={() => setView('front')}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${
            view === 'front'
              ? 'bg-purple-500 text-white'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Front View
        </button>
        <button
          type="button"
          onClick={() => setView('back')}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-all ${
            view === 'back'
              ? 'bg-purple-500 text-white'
              : 'text-gray-400 hover:text-white'
          }`}
        >
          Back View
        </button>
      </div>

      {/* Body Diagram */}
      <div className="relative bg-gradient-to-b from-slate-800/50 to-slate-900/50 rounded-2xl p-4 border border-white/10">
        <div className="flex justify-center">
          <svg 
            viewBox="0 0 300 700" 
            className="w-full max-w-[200px] h-auto"
            style={{ maxHeight: '400px' }}
          >
            {/* Body outline */}
            <defs>
              <linearGradient id="bodyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.1" />
              </linearGradient>
            </defs>

            {/* Human silhouette base */}
            <ellipse cx="150" cy="72" rx="50" ry="55" fill="url(#bodyGradient)" stroke="#6366f1" strokeWidth="1" opacity="0.5" />
            <rect x="135" y="125" width="30" height="25" rx="5" fill="url(#bodyGradient)" stroke="#6366f1" strokeWidth="1" opacity="0.5" />
            <path d="M60,150 L100,150 L100,150 L210,250 L200,340 L190,380 L110,380 L100,340 L90,250 L100,150 L60,170 L40,280 L40,385 L20,410 L65,410 L75,280 L75,180 L100,150 L200,150 L225,180 L225,280 L235,410 L280,410 L260,280 L240,170 L200,150 L210,250 L200,340 L190,380 L150,380 L150,360 L145,470 L145,510 L135,620 L145,670 L85,670 L100,620 L105,510 L105,470 L110,380 L150,380 L155,470 L155,510 L165,620 L155,670 L215,670 L200,620 L195,510 L195,470 L190,380 Z" 
              fill="url(#bodyGradient)" stroke="#6366f1" strokeWidth="1" opacity="0.3" />

            {/* Interactive regions */}
            {currentRegions.map((region) => {
              const injury = injuries.find(i => i.regionId === region.id);
              const injuryType = injury ? INJURY_TYPES.find(t => t.id === injury.injuryType) : null;
              
              return (
                <g key={region.id} onClick={() => handleRegionClick(region.id)} style={{ cursor: 'pointer' }}>
                  <path
                    d={region.path}
                    fill={getRegionColor(region.id)}
                    fillOpacity={isRegionSelected(region.id) ? 0.6 : 0.1}
                    stroke={isRegionSelected(region.id) ? (injuryType?.color || '#a855f7') : '#6366f1'}
                    strokeWidth={isRegionSelected(region.id) ? 2 : 1}
                    strokeOpacity={0.5}
                    className="transition-all duration-200 hover:fill-opacity-40 hover:stroke-opacity-100"
                  />
                  {injury && (
                    <text
                      x={region.cx}
                      y={region.cy}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize="16"
                      className="pointer-events-none"
                    >
                      {injuryType?.icon}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* View indicator */}
        <div className="absolute bottom-2 left-2 flex items-center gap-1 text-xs text-gray-500">
          <RotateCcw className="w-3 h-3" />
          {view === 'front' ? 'Front' : 'Back'}
        </div>

        {/* Tap instruction */}
        <p className="text-center text-xs text-gray-500 mt-2">
          Tap a body part to add an injury
        </p>
      </div>

      {/* Injury Type Selection Modal */}
      {showInjuryTypes && selectedRegion && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-white/20 rounded-t-3xl w-full max-w-lg p-6 animate-slide-up">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-white">Select Injury Type</h3>
                <p className="text-sm text-gray-400">
                  {currentRegions.find(r => r.id === selectedRegion)?.label}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowInjuryTypes(false);
                  setSelectedRegion(null);
                }}
                className="p-2 hover:bg-white/10 rounded-full transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {INJURY_TYPES.map((type) => (
                <button
                  key={type.id}
                  type="button"
                  onClick={() => handleInjuryTypeSelect(type.id)}
                  className="flex items-center gap-3 p-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-all text-left"
                  style={{ borderColor: `${type.color}33` }}
                >
                  <span className="text-xl">{type.icon}</span>
                  <span className="text-sm text-white font-medium">{type.label}</span>
                </button>
              ))}
            </div>

            {/* Remove injury option if already exists */}
            {injuries.some(i => i.regionId === selectedRegion) && (
              <button
                type="button"
                onClick={() => {
                  removeInjury(selectedRegion);
                  setShowInjuryTypes(false);
                  setSelectedRegion(null);
                }}
                className="w-full mt-3 p-3 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded-xl text-red-400 font-medium transition-all"
              >
                Remove Injury
              </button>
            )}
          </div>
        </div>
      )}

      {/* Selected Injuries Summary */}
      {injuries.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-300">Injuries Selected ({injuries.length})</h4>
          <div className="space-y-2">
            {injuries.map((injury) => {
              const type = INJURY_TYPES.find(t => t.id === injury.injuryType);
              return (
                <div
                  key={injury.regionId}
                  className="flex items-center justify-between p-3 bg-white/5 border border-white/10 rounded-xl"
                  style={{ borderLeftColor: type?.color, borderLeftWidth: '3px' }}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{type?.icon}</span>
                    <div>
                      <p className="text-sm font-medium text-white">{injury.regionLabel}</p>
                      <p className="text-xs text-gray-400">{injury.injuryLabel}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeInjury(injury.regionId)}
                    className="p-1.5 hover:bg-red-500/20 rounded-full transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-400 hover:text-red-400" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
