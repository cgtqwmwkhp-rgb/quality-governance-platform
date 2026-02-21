/**
 * CollaboratorCursors - Shows remote collaborator cursors
 *
 * Features:
 * - Colored cursor indicators per collaborator
 * - Name labels on hover
 * - Animated transitions
 */

import React from "react";

interface Collaborator {
  id: string;
  name: string;
  color: string;
  cursor?: {
    index: number;
    length: number;
  };
}

interface CollaboratorCursorsProps {
  collaborators: Collaborator[];
  containerRef?: React.RefObject<HTMLElement>;
}

const CollaboratorCursors: React.FC<CollaboratorCursorsProps> = ({
  collaborators,
  // containerRef is reserved for future DOM cursor positioning
}) => {
  // For now, just show presence indicators
  // Full cursor positioning requires DOM measurements

  if (collaborators.length === 0) {
    return null;
  }

  return (
    <div className="absolute top-2 right-2 flex items-center gap-1">
      {collaborators.map((collaborator) => (
        <div
          key={collaborator.id}
          className="relative group"
          title={`${collaborator.name} is editing`}
        >
          {/* Cursor dot */}
          <div
            className="w-3 h-3 rounded-full border-2 border-white shadow-sm animate-pulse"
            style={{ backgroundColor: collaborator.color }}
          />

          {/* Name tooltip */}
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-slate-800 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            {collaborator.name}
            <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
          </div>
        </div>
      ))}

      {/* Count badge if many collaborators */}
      {collaborators.length > 3 && (
        <div className="w-6 h-6 rounded-full bg-slate-700 text-white text-xs flex items-center justify-center font-medium">
          +{collaborators.length - 3}
        </div>
      )}
    </div>
  );
};

export default CollaboratorCursors;
