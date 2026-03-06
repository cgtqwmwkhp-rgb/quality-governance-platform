import { useNavigate } from 'react-router-dom';

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="text-6xl font-bold text-gray-300 mb-4">404</div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-2">Page not found</h1>
      <p className="text-gray-500 mb-8 max-w-md">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <div className="flex gap-3">
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Go back
        </button>
        <button
          onClick={() => navigate('/dashboard')}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  );
}
