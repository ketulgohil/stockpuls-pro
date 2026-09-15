{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.uvicorn
    pkgs.python311Packages.fastapi
    pkgs.python311Packages.yfinance
    pkgs.python311Packages.pandas
    pkgs.python311Packages.numpy
    pkgs.python311Packages.requests
  ];
}
