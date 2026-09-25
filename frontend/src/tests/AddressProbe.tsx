import { useLocation } from 'react-router-dom';

// What the address bar would show, for a test to read.
function AddressProbe() {
  const location = useLocation();
  return (
    <output data-testid="address" hidden>
      {location.pathname + location.search}
    </output>
  );
}

export default AddressProbe;
