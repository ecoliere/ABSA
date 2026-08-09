import { useState } from 'react';
import { X, Plus, Trash2 } from 'lucide-react';

interface Aspect {
  name: string;
  count: number;
}

interface AspectGroup {
  id: string;
  name: string;
  aspects: string[];
}

interface MergeAspectModalProps {
  isOpen: boolean;
  onClose: () => void;
  aspects: Aspect[];
  groups: AspectGroup[];
  onCreateGroup: (name: string, aspectNames: string[]) => void;
  onDeleteGroup: (groupId: string) => void;
}

export default function MergeAspectModal({
  isOpen,
  onClose,
  aspects,
  groups,
  onCreateGroup,
  onDeleteGroup,
}: MergeAspectModalProps) {
  const [selectedAspects, setSelectedAspects] = useState<string[]>([]);
  const [groupName, setGroupName] = useState('');

  if (!isOpen) return null;

  const handleToggleAspect = (aspectName: string) => {
    setSelectedAspects((prev) =>
      prev.includes(aspectName)
        ? prev.filter((name) => name !== aspectName)
        : [...prev, aspectName]
    );
  };

  const handleCreateGroup = () => {
    if (groupName.trim() && selectedAspects.length >= 2) {
      onCreateGroup(groupName.trim(), selectedAspects);
      setGroupName('');
      setSelectedAspects([]);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white border border-zinc-300 rounded w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="border-b border-zinc-300 px-6 py-4 flex items-center justify-between">
          <h2 className="text-base font-medium text-zinc-900">Управление группами аспектов</h2>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-6">
            <h3 className="text-sm font-medium text-zinc-900 mb-3">Создать новую группу</h3>
            <input
              type="text"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              placeholder="Название группы"
              className="w-full px-4 py-2 border border-zinc-300 rounded text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent mb-3"
            />

            <div className="border border-zinc-300 rounded">
              <div className="bg-zinc-50 px-4 py-2 border-b border-zinc-300">
                <span className="text-xs font-medium text-zinc-600 uppercase">
                  Выберите аспекты для объединения (минимум 2)
                </span>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {aspects.map((aspect, idx) => (
                  <label
                    key={idx}
                    className="flex items-center px-4 py-3 hover:bg-zinc-50 cursor-pointer border-b border-zinc-200 last:border-0"
                  >
                    <input
                      type="checkbox"
                      checked={selectedAspects.includes(aspect.name)}
                      onChange={() => handleToggleAspect(aspect.name)}
                      className="w-4 h-4 border-zinc-300 rounded text-zinc-900 focus:ring-2 focus:ring-zinc-400"
                    />
                    <span className="ml-3 text-sm text-zinc-900">{aspect.name}</span>
                    <span className="ml-auto text-xs text-zinc-500">({aspect.count})</span>
                  </label>
                ))}
              </div>
            </div>

            <button
              onClick={handleCreateGroup}
              disabled={!groupName.trim() || selectedAspects.length < 2}
              className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2 bg-zinc-900 text-white text-sm font-medium rounded hover:bg-zinc-800 disabled:bg-zinc-300 disabled:cursor-not-allowed"
            >
              <Plus className="w-4 h-4" />
              Создать группу
            </button>
          </div>

          {groups.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-zinc-900 mb-3">Существующие группы</h3>
              <div className="space-y-3">
                {groups.map((group) => (
                  <div key={group.id} className="border border-zinc-300 rounded">
                    <div className="px-4 py-3 flex items-start justify-between">
                      <div className="flex-1">
                        <div className="text-sm font-medium text-zinc-900 mb-2">
                          {group.name}
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {group.aspects.map((aspect, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 bg-zinc-100 text-zinc-700 text-xs rounded"
                            >
                              {aspect}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button
                        onClick={() => onDeleteGroup(group.id)}
                        className="ml-4 text-zinc-400 hover:text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="border-t border-zinc-300 px-6 py-4">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 border border-zinc-300 rounded text-sm font-medium text-zinc-900 hover:bg-zinc-50"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
